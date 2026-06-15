import argparse
import json
import os
import re
import sys
import time
import pandas as pd

# Config centralizada (antes COURSE estava fixo no topo deste script).
sys.path.insert(0, "src")
from spm.config import COURSE



def save_to_csv(list_of_dataframes):
    for df in list_of_dataframes:
        if not os.path.exists(f"./outputs/sceneries/{COURSE}"):
            os.makedirs(f"./outputs/sceneries/{COURSE}")
        df["data"].to_csv(f"./outputs/sceneries/{COURSE}/{df['name']}.csv")


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


def read_params(argv=None) -> dict:
    parser = argparse.ArgumentParser(description="Process command-line parameters for temporal folding and file paths.")

    parser.add_argument("-p", "--path", type=str, required=True, help="Path of the log file")
    parser.add_argument("-sp", "--save-path", type=str, required=True, help="Path to save the file")
    parser.add_argument("-pg", "--grade-path", type=str, required=True, help="Path of grades CSV file")
    parser.add_argument("-pq", "--quiz-path", type=str, required=True, help="Path of quiz CSV file")
    parser.add_argument("-mp", "--mapping-path", type=str, required=True, help="Path of event mapping CSV file")
    parser.add_argument("-act", "--activity", type=int, required=True, help="Activity ID")
    parser.add_argument("-id", "--assignment-id", type=int, required=True, help="Assignment ID")
    parser.add_argument("-tf", "--temporal-folding", action="store_true", help="Enable temporal folding")
    parser.add_argument("-m", "--multilevel", action="store_true", help="Enable multilevel sequential patterns")
    parser.add_argument("-r", "--coalescing-repeating", action="store_true", help="Enable coalescing repeating")
    parser.add_argument("-c", "--coalescing-hidden", action="store_true", help="Enable coalescing hidden")
    parser.add_argument(
        "-s", "--spell", action="store_true", help="Enable spell option and disable coalescing repeating"
    )

    parser.add_argument(
        "--split-grade", action="store_true", help="Split datasets into high-grade and low-grade before simplification"
    )

    # Parse the arguments
    # args = parser.parse_args(argv)
    args = parser.parse_args(argv[1:] if argv else None)

    # Prepare the params dictionary with parsed arguments
    params = {
        "path": args.save_path,
        "grade_path": args.grade_path,
        "quiz_path": args.quiz_path,
        "activity": args.activity,
        "assignment_id": args.assignment_id,
        "tf": args.temporal_folding,
        "coalescing_repeating": args.coalescing_repeating,
        "coalescing_hidden": args.coalescing_hidden,
        "spell": args.spell,
        "multilevel": args.multilevel,
        "data": pd.read_csv(args.path, index_col="id").sort_values("t"),
        "mapping": pd.read_csv(args.mapping_path),
        "quiz": pd.read_csv(args.quiz_path),
        "split_grade": args.split_grade,
    }

    # Override coalescing_repeating if spell option is enabled
    if args.spell:
        params["coalescing_repeating"] = False

    params = get_dates(params)

    return params


def main(params: dict):
    if params["grade_path"]:
        grade_df = pd.read_csv(params["grade_path"])
    first_access, activity, grades = partitioning(params, grade_df)
    activity = classify_events(activity, first_access)

    events_by_user = prepare_database(activity, params, grades)
    os.makedirs(params["path"], exist_ok=True)

    if params["split_grade"]:
        high_grade, low_grade = split_by_grade(events_by_user)

        with open(params["path"] + "high.json", "w+") as file:
            json.dump(high_grade, file, indent=2, default=lambda o: str(o))

        with open(params["path"] + "low.json", "w+") as file:
            json.dump(low_grade, file, indent=2, default=lambda o: str(o))
    else:
        with open(params["path"] + "user.json", "w+") as file:
            json.dump(events_by_user, file, indent=2, default=lambda o: str(o))


def ready_main(params: dict):
    activities_details = [
        {"initial_date": 1573700400, "final_date": 1574391540, "assignment_id": 12874},
        {"initial_date": 1574305200, "final_date": 1574996340, "assignment_id": 12875},
        {"initial_date": 1574910000, "final_date": 1575600900, "assignment_id": 12876},

        # {"initial_date": 1573527600, "final_date": 1574218500, "assignment_id": 12841},
        # {"initial_date": 1574132400, "final_date": 1574823300, "assignment_id": 12842},
        # {"initial_date": 1574737200, "final_date": 1575428100, "assignment_id": 12843},
        # {"initial_date": 1575342000, "final_date": 1576032900, "assignment_id": 12844},
    ]
    params["grade_path"] = f"./data/raw/{COURSE}/see_course{COURSE}_quiz_grades.csv"
    params["data"] = pd.read_csv(f"./data/raw/{COURSE}/see_course{COURSE}_logs_filtered.csv", index_col="id").sort_values("t")
    params["mapping"] = pd.read_csv(f"./data/raw/{COURSE}/event_mapping.csv")
    params["quiz"] = pd.read_csv(f"./data/raw/{COURSE}/see_course{COURSE}_quiz_list.csv")
    params["split_grade"] = False
    for activity in range(1, len(activities_details) + 1):
        params["activity"] = activity
        params["initial_date"] = activities_details[activity - 1]["initial_date"]
        params["final_date"] = activities_details[activity - 1]["final_date"]
        params["assignment_id"] = activities_details[activity - 1]["assignment_id"]

        grade_df = None
        sceneries_names = [
            # {"path": "0-zero", "multilevel": False, "spell": False, "coalescing_repeating": False, "coalescing_hidden": False, "tf": False, "remove_temporal_windowing": True, "remove_event_category_extraction": True},
            {"path": "0-zero", "multilevel": False, "spell": False, "coalescing_repeating": False, "coalescing_hidden": False, "tf": False},
            {"path": "1-first", "multilevel": True, "spell": False, "coalescing_repeating": True, "coalescing_hidden": True, "tf": False},
            {"path": "2-second", "multilevel": True, "spell": False, "coalescing_repeating": True, "coalescing_hidden": False, "tf": False},
            {"path": "3-third", "multilevel": True, "spell": False, "coalescing_repeating": False, "coalescing_hidden": True, "tf": False},

            {"path": "4-fourth", "multilevel": True, "spell": False, "coalescing_repeating": False, "coalescing_hidden": False, "tf": False},
            {"path": "5-fifth", "multilevel": False, "spell": False, "coalescing_repeating": True, "coalescing_hidden": True, "tf": False},
            {"path": "6-sixth", "multilevel": False, "spell": False, "coalescing_repeating": True, "coalescing_hidden": False, "tf": False},
            {"path": "7-seventh", "multilevel": False, "spell": False, "coalescing_repeating": False, "coalescing_hidden": True, "tf": False},

            {"path": "8-eighth", "multilevel": True, "spell": True, "coalescing_hidden": True, "coalescing_repeating": False, "tf": False},
            {"path": "9-ninth", "multilevel": True, "spell": True, "coalescing_hidden": False, "coalescing_repeating": False, "tf": False},
            {"path": "10-tenth", "multilevel": False, "spell": True, "coalescing_hidden": True, "coalescing_repeating": False, "tf": False},
            {"path": "11-eleventh", "multilevel": False, "spell": True, "coalescing_hidden": False, "coalescing_repeating": False, "tf": False},

            {"path": "12-twelfth", "multilevel": True, "spell": False, "coalescing_repeating": True, "coalescing_hidden": True, "tf": True},
            {"path": "13-thirteenth", "multilevel": True, "spell": False, "coalescing_repeating": True, "coalescing_hidden": False, "tf": True},
            {"path": "14-fourteenth", "multilevel": True, "spell": False, "coalescing_repeating": False, "coalescing_hidden": True, "tf": True},
            {"path": "15-fifteenth", "multilevel": True, "spell": False, "coalescing_repeating": False, "coalescing_hidden": False, "tf": True},

            {"path": "16-sixteenth", "multilevel": False, "spell": False, "coalescing_repeating": True, "coalescing_hidden": True, "tf": True},
            {"path": "17-seventeenth", "multilevel": False, "spell": False, "coalescing_repeating": True, "coalescing_hidden": False, "tf": True},
            {"path": "18-eighteenth", "multilevel": False, "spell": False, "coalescing_repeating": False, "coalescing_hidden": True, "tf": True},
            {"path": "19-nineteenth", "multilevel": False, "spell": False, "coalescing_repeating": False, "coalescing_hidden": False, "tf": True},

            {"path": "20-twentieth", "multilevel": True, "spell": True, "coalescing_hidden": True, "coalescing_repeating": False, "tf": True},
            {"path": "21-twenty_first", "multilevel": True, "spell": True, "coalescing_hidden": False, "coalescing_repeating": False, "tf": True},
            {"path": "22-twenty_second", "multilevel": False, "spell": True, "coalescing_hidden": True, "coalescing_repeating": False, "tf": True},
            {"path": "23-twenty_third", "multilevel": False, "spell": True, "coalescing_hidden": False, "coalescing_repeating": False, "tf": True},
        ]
        for scenery in sceneries_names:
            start = time.time()
            params["multilevel"] = scenery["multilevel"]
            params["coalescing_repeating"] = scenery["coalescing_repeating"]
            params["coalescing_hidden"] = scenery["coalescing_hidden"]
            params["spell"] = scenery["spell"]
            params["tf"] = scenery["tf"]
            if params["split_grade"]:
                params["path"] = f"outputs/sceneries/{COURSE}/{params["activity"]}/split_grade/{scenery['path']}"
            else:
                params["path"] = f"outputs/sceneries/{COURSE}/{params["activity"]}/{scenery['path']}"

            if params["grade_path"]:
                grade_df = pd.read_csv(params["grade_path"])
            first_access, activity, grades = partitioning(params, grade_df)
            activity = classify_events(activity, first_access)

            events_by_user = prepare_database(activity, params, grades)

            os.makedirs(f"./outputs/sceneries/{COURSE}/" + str(params["activity"]), exist_ok=True)

            os.makedirs(f"./outputs/sceneries/{COURSE}/" + str(params["activity"]) + "/split_grade", exist_ok=True)

            if params["split_grade"]:
                print(f"Splitting dataset into high-grade and low-grade, {params["path"]}")
                high_grade, low_grade = split_by_grade(events_by_user)

                with open(params["path"] + "_high.json", "w+") as file:
                    json.dump(high_grade, file, indent=2, default=lambda o: str(o))

                with open(params["path"] + "_low.json", "w+") as file:
                    json.dump(low_grade, file, indent=2, default=lambda o: str(o))
            else:
                with open(params["path"] + ".json", "w+") as file:
                    json.dump(events_by_user, file, indent=2, default=lambda o: str(o))
            print(f"Execution time, {params["path"]}: {(time.time() - start):.2f}")
        print()


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "test":
        ready_main({})
    else:
        main(read_params(sys.argv))
