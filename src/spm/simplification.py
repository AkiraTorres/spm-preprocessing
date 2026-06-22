"""Núcleo de pré-processamento (simplificação) das sequências de eventos.

Transforma logs crus do Moodle em sequências de eventos catalogados, aplicando
as técnicas de simplificação de cada cenário (multilevel, temporal folding,
coalescing, spell). Todas as funções operam em memória sobre DataFrames/listas
e parâmetros explícitos — não tocam em disco.

A função de alto nível é :func:`simplify`, que recebe os logs, o mapeamento de
eventos e um cenário (dict de flags) e devolve a lista de sequências por usuário.
A orquestração baseada em arquivos (ler CSVs, iterar os 24 cenários, gravar JSON)
fica em :mod:`spm.pipeline`.
"""
import re

import pandas as pd


def event_mapping(event, t: int, params: dict):
    mapping = params["mapping"]
    mapped = mapping[(mapping.component == event[0]) & (mapping.action == event[1]) & (mapping.target == event[2])]
    e = mapped["class"].iloc[0]
    result = {"event": e, "time": t}
    if params["multilevel"]:
        tf = params["initial_date"] + (params["final_date"] - params["initial_date"]) / 2
        e = e + "_START" if t <= tf else e + "_END"
        result = {"event": e, "time": t}

    return result


def temporal_folding(events, session_gap=3600):
    sessions = []
    current_session = [events[0]]

    for i in range(1, len(events)):
        if events[i]["time"] - events[i - 1]["time"] <= session_gap:
            current_session.append(events[i])
        else:
            sessions.append(current_session)
            current_session = [events[i]]

    sessions.append(current_session)
    return sessions


def coalescing_hidden(events, multilevel=False):
    remove_indexes = []
    suffix = "_START" if multilevel else ""
    end_suffix = "_END" if multilevel else ""

    for i in range(len(events) - 1):
        try:
            if events[i]["event"] == f"assignment_vis{suffix}" and events[i + 1]["event"] in [
                f"assignment_try{suffix}",
                f"assignment_sub{suffix}",
            ]:
                remove_indexes.append(i)
            elif (
                events[i]["event"] == f"assignment_try{suffix}" and events[i + 1]["event"] == f"assignment_sub{suffix}"
            ):
                remove_indexes.append(i)
            elif (
                multilevel
                and events[i]["event"] == f"assignment_vis{end_suffix}"
                and events[i + 1]["event"] in [f"assignment_try{end_suffix}", f"assignment_sub{end_suffix}"]
            ):
                remove_indexes.append(i)
            elif (
                multilevel
                and events[i]["event"] == f"assignment_try{end_suffix}"
                and events[i + 1]["event"] == f"assignment_sub{end_suffix}"
            ):
                remove_indexes.append(i)
        except IndexError:
            pass

    # get index list in reverse order
    remove_indexes = sorted(remove_indexes, reverse=True)
    # drop elements in place
    for index in remove_indexes:
        del events[index]


def coalescing_repeating(events):
    remove_indexes = []
    for i in range(len(events)):
        try:
            if events[i]["event"] == events[i + 1]["event"]:
                if re.match(r"^assignment_sub(_START|_END)?$", events[i]["event"]):
                    remove_indexes.append(i)
                else:
                    remove_indexes.append(i + 1)
        except IndexError:
            pass
    # get index list in reverse order
    remove_indexes = sorted(remove_indexes, reverse=True)
    # drop elements in place
    for index in remove_indexes:
        del events[index]


def spell(events):
    remove_indexes = []
    for i in range(len(events)):
        try:
            spell_length = 1
            index = i
            while events[index]["event"] == events[index + 1]["event"]:
                spell_length += 1
                index += 1
            if events[i]["event"] == events[i + 1]["event"]:
                if re.match(r"^assignment_sub(_START|_END)?$", events[i]["event"]):
                    remove_indexes.append(i)
                else:
                    remove_indexes.append(i + 1)
            # events[i]["event"] = events[i]["event"] + f"-{spell_length}"
            if 2 < spell_length <= 5:
                events[i]["event"] = events[i]["event"] + f"_SOME"
            elif spell_length > 5:
                events[i]["event"] = events[i]["event"] + f"_MANY"
        except IndexError:
            pass
    # get index list in reverse order
    remove_indexes = sorted(remove_indexes, reverse=True)
    # drop elements in place
    for index in remove_indexes:
        del events[index]


# return a sequence of catalogued events based on a dataframe of events
def generate_sequence_from_df(df, params: dict):
    e = list(df.apply(lambda x: event_mapping([x.component, x.action, x.target], x.t, params), axis=1))
    if True or params.get("remove_temporal_windowing"):
        e.pop(0)
    flag = False
    events = []
    # collect events after the last submission event
    if True or params.get("remove_event_category_extraction"):
        for event in reversed(e):
            if (re.match(r"^assignment_sub(_START|_END)?$", event["event"])) and not flag:
                flag = True
            if flag:
                events.append(event)
    else:
        events = e
    events = list(reversed(events))

    if not events:
        return None

    if params["tf"]:
        sessions = temporal_folding(events)

    else:
        sessions = [events]

    for session in sessions:
        if params["coalescing_repeating"]:
            coalescing_repeating(session)
        if params["coalescing_hidden"]:
            coalescing_hidden(session, params["multilevel"])
        if params["spell"]:
            spell(session)
    return sessions


# make the database ready for GSP and prefix datamining algorithms
def prepare_database(df, params: dict, grade_df=None) -> list:
    events_by_user = []
    unique_users = df.drop_duplicates(subset=["userid"])
    unique_users = unique_users["userid"].tolist()

    for userid in unique_users:
        events = generate_sequence_from_df(df[df.userid == userid], params)
        if events:
            new_user = {"key": str(userid), "events": events, "temporal_folding": params["tf"]}
            if grade_df is not None and not grade_df.empty:
                user_grade = grade_df.query(f"userid == {userid}")["student_grade"]
                if user_grade.empty:
                    user_grade = 0.0
                else:
                    user_grade = user_grade.iloc[0]
                new_user["grade"] = user_grade
                new_user["max_grade"] = grade_df["max_grade"].iloc[0]
            events_by_user.append(new_user)
    return events_by_user


def partitioning(params, grade_df=None):
    all_logs_data = params["data"]

    init_date = params["initial_date"]
    final_date = params["final_date"]
    assignment_id = params["assignment_id"]
    grades = None
    activity_logs = (
        all_logs_data.sort_values("t")
        .query(f"t >= {init_date} & t <= {final_date}")
        .query(f"assignment_id == {assignment_id} | component != 'core' & component != 'mod_page'")
    )

    first_access = all_logs_data.sort_values("t").drop_duplicates(subset=["userid"])
    first_access = first_access.sort_values("userid")

    if grade_df is not None:
        grades = grade_df.query(f"id == {assignment_id}")

    return [first_access, activity_logs, grades]


def classify_events(activity, first_access):
    return pd.concat([first_access, activity])


def get_dates(quiz_df, assignment_id):
    """Deriva (t_open, t_close) de uma atividade a partir do CSV de quizzes."""
    t_open = quiz_df.query(f"id == {assignment_id}")["t_open"].iloc[0]
    t_close = quiz_df.query(f"id == {assignment_id}")["t_close"].iloc[0]
    return t_open, t_close


def split_by_grade(prepared_data, threshold=0.5):
    high_grade = []
    low_grade = []

    for user in prepared_data:
        if user.get("grade", 0) / user.get("max_grade", 2) >= threshold:
            high_grade.append(user)
        else:
            low_grade.append(user)

    return high_grade, low_grade


def simplify(logs_df, mapping_df, scenario, *, assignment_id, initial_date, final_date,
             grades_df=None, split_grade=False):
    """Simplifica os logs de uma atividade segundo um cenário, em memória.

    Args:
        logs_df: DataFrame de logs crus do Moodle (colunas userid, t, component,
            action, target, assignment_id, ...).
        mapping_df: DataFrame de mapeamento de eventos (component/action/target -> class).
        scenario: dict com as flags do cenário (multilevel, spell,
            coalescing_repeating, coalescing_hidden, tf) — ver
            :data:`spm.sceneries.SCENERY_DEFINITIONS`.
        assignment_id: ID da atividade a recortar dos logs.
        initial_date, final_date: janela temporal (timestamps) da atividade;
            normalmente derivada do quiz CSV via :func:`get_dates`.
        grades_df: DataFrame de notas (opcional); se dado, anexa grade/max_grade.
        split_grade: se True, devolve ``(high, low)`` separados por nota.

    Returns:
        Lista de sequências por usuário (``events_by_user``), ou a tupla
        ``(high_grade, low_grade)`` quando ``split_grade=True``.
    """
    params = {
        "data": logs_df.sort_values("t"),
        "mapping": mapping_df,
        "assignment_id": assignment_id,
        "initial_date": initial_date,
        "final_date": final_date,
        "multilevel": scenario["multilevel"],
        "coalescing_repeating": scenario["coalescing_repeating"],
        "coalescing_hidden": scenario["coalescing_hidden"],
        "spell": scenario["spell"],
        "tf": scenario["tf"],
    }

    first_access, activity_logs, grades = partitioning(params, grades_df)
    activity_logs = classify_events(activity_logs, first_access)
    events_by_user = prepare_database(activity_logs, params, grades)

    if split_grade:
        return split_by_grade(events_by_user)
    return events_by_user
