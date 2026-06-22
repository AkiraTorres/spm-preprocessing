import argparse
import json
import os
import re
import sys
import time
import pandas as pd

# Matriz de cenarios (fonte unica). Todos os parametros de execucao
# (curso, atividade, assignment_id, paths) vem por flags de CLI.
sys.path.insert(0, "src")
from spm.sceneries import SCENERY_DEFINITIONS


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

    # if params["coalescing_repeating"]:
    #     coalescing_repeating(events)
    #
    # if params["coalescing_hidden"]:
    #     coalescing_hidden(events, params["multilevel"])
    #
    # if params["spell"]:
    #     spell(events)
    #
    # return events


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
                # print(userid)
                user_grade = grade_df.query(f"userid == {userid}")["student_grade"]
                if user_grade.empty:
                    user_grade = 0.0
                else:
                    user_grade = user_grade.iloc[0]
                new_user["grade"] = user_grade
                new_user["max_grade"] = grade_df["max_grade"].iloc[0]
            events_by_user.append(new_user)
    # print(json.dumps(events_by_user[0], indent=2, default=lambda o: str(o)))
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
        # .query(f"t >= 1573527600 & t <= 1574218500")
    )

    first_access = all_logs_data.sort_values("t").drop_duplicates(subset=["userid"])
    first_access = first_access.sort_values("userid")

    if grade_df is not None:
        grades = grade_df.query(f"id == {assignment_id}")
        # .query(f"time_open >= {init_date} & time_close <= {final_date}"))  # ["userid", "student_grade", "max_grade"]

    return [first_access, activity_logs, grades]


def classify_events(activity, first_access):
    return pd.concat([first_access, activity])  # .sort_values("userid")


def get_dates(params: dict) -> dict:
    quiz = params["quiz"]

    t_open = quiz.query(f"id == {params["assignment_id"]}")["t_open"].iloc[0]
    t_close = quiz.query(f"id == {params["assignment_id"]}")["t_close"].iloc[0]

    params["initial_date"] = t_open
    params["final_date"] = t_close

    return params


def split_by_grade(prepared_data, threshold=0.5):
    high_grade = []
    low_grade = []

    for user in prepared_data:
        if user.get("grade", 0) / user.get("max_grade", 2) >= threshold:
            high_grade.append(user)
        else:
            low_grade.append(user)

    return high_grade, low_grade


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Pre-processa logs do Moodle gerando um JSON por cenario da matriz "
        "(outputs/sceneries/{course}/{activity}/{scenery}.json)."
    )
    parser.add_argument("-co", "--course", type=int, required=True, help="Numero do curso (ex.: 2060, 2065)")
    parser.add_argument("-act", "--activity", type=int, required=True, help="Numero da atividade (inteiro)")
    parser.add_argument(
        "-id", "--assignment-id", type=int, required=True,
        help="Assignment ID da atividade; as datas (t_open/t_close) sao derivadas do quiz CSV",
    )
    parser.add_argument(
        "--logs", type=str, default=None,
        help="CSV de logs (default: data/raw/{course}/see_course{course}_logs_filtered.csv)",
    )
    parser.add_argument(
        "--grades", type=str, default=None,
        help="CSV de notas (default: data/raw/{course}/see_course{course}_quiz_grades.csv)",
    )
    parser.add_argument(
        "--quiz", type=str, default=None,
        help="CSV da lista de quizzes (default: data/raw/{course}/see_course{course}_quiz_list.csv)",
    )
    parser.add_argument(
        "--mapping", type=str, default=None,
        help="CSV de mapeamento de eventos (default: data/raw/{course}/event_mapping.csv)",
    )
    parser.add_argument(
        "--out-dir", type=str, default="outputs/sceneries",
        help="Raiz de saida dos cenarios (default: outputs/sceneries)",
    )
    parser.add_argument("--split-grade", action="store_true", help="Gera variantes _high/_low por nota")
    return parser.parse_args(argv)


def build_params(args) -> dict:
    course = args.course
    base = f"data/raw/{course}"
    logs = args.logs or f"{base}/see_course{course}_logs_filtered.csv"
    grades = args.grades or f"{base}/see_course{course}_quiz_grades.csv"
    quiz = args.quiz or f"{base}/see_course{course}_quiz_list.csv"
    mapping = args.mapping or f"{base}/event_mapping.csv"

    params = {
        "course": course,
        "activity": args.activity,
        "assignment_id": args.assignment_id,
        "grade_path": grades,
        "data": pd.read_csv(logs, index_col="id").sort_values("t"),
        "mapping": pd.read_csv(mapping),
        "quiz": pd.read_csv(quiz),
        "split_grade": args.split_grade,
    }
    # Deriva initial_date/final_date (t_open/t_close) a partir do quiz CSV.
    params = get_dates(params)
    return params


def run(args) -> None:
    params = build_params(args)
    course = params["course"]
    activity = params["activity"]
    scenery_dir = f"{args.out_dir}/{course}/{activity}"
    os.makedirs(scenery_dir, exist_ok=True)
    if params["split_grade"]:
        os.makedirs(f"{scenery_dir}/split_grade", exist_ok=True)

    grade_df = pd.read_csv(params["grade_path"]) if params["grade_path"] else None

    print(f"Simplificacao | curso {course} atividade {activity} assignment {params['assignment_id']}")
    print(f"  datas (do quiz CSV): {params['initial_date']} -> {params['final_date']}")
    print(f"  cenarios: {len(SCENERY_DEFINITIONS)} -> {scenery_dir}\n")

    for scenery in SCENERY_DEFINITIONS:
        start = time.time()
        params["multilevel"] = scenery["multilevel"]
        params["coalescing_repeating"] = scenery["coalescing_repeating"]
        params["coalescing_hidden"] = scenery["coalescing_hidden"]
        params["spell"] = scenery["spell"]
        params["tf"] = scenery["tf"]

        first_access, activity_logs, grades = partitioning(params, grade_df)
        activity_logs = classify_events(activity_logs, first_access)
        events_by_user = prepare_database(activity_logs, params, grades)

        if params["split_grade"]:
            high_grade, low_grade = split_by_grade(events_by_user)
            base = f"{scenery_dir}/split_grade/{scenery['path']}"
            with open(base + "_high.json", "w+") as file:
                json.dump(high_grade, file, indent=2, default=lambda o: str(o))
            with open(base + "_low.json", "w+") as file:
                json.dump(low_grade, file, indent=2, default=lambda o: str(o))
            out = base + "_{high,low}.json"
        else:
            out = f"{scenery_dir}/{scenery['path']}.json"
            with open(out, "w+") as file:
                json.dump(events_by_user, file, indent=2, default=lambda o: str(o))
        print(f"  {scenery['path']}: {(time.time() - start):.2f}s -> {out}")


if __name__ == "__main__":
    run(parse_args())
