import requests
import json
import csv
import time
import base64
from bs4 import BeautifulSoup

def get_all_leaderboard_runs(params):
    page = 1
    backoff = 1
    while True:
        query = base64.b64encode(bytes(json.dumps({ "params": params, "page": page, "vary": 1724634016 }), 'utf-8')).decode("utf-8").rstrip("=")
        r = requests.get(f"https://www.speedrun.com/api/v2/GetGameLeaderboard2?_r={query}")
        data = json.loads(r.text)
        if data.get("error") == "Rate limited. Please try again later.":
            print(f"rate limited -- sleeping for {backoff} seconds")
            time.sleep(backoff)
            backoff *= 2
            continue
        else:
            backoff = 1
        if not "pagination" in data:
            print(query)
            raise
        total_pages = data["pagination"]["pages"]
        for run in json.loads(r.text)["runList"]:
            yield run
        if page >= total_pages:
            return
        page += 1

BASE_PATH="https://www.speedrun.com/api"

def get_all(base_query):
    cnt = 200 #max is 200
    offset = 0
    while True:
        if offset >= 10000: #can't handle > 10000 runs TODO try api v2 instead
            break
        print(base_query + f"&offset={offset}&max={cnt}")
        r = requests.get(base_query + f"&offset={offset}&max={cnt}")
        time.sleep(1)
        res = json.loads(r.text)["data"]
        if "y8xk0odm" in r.text:
            print("found it")
        if len(res) == 0:
            break
        for x in res:
            yield x
        offset += cnt

def group_by(l, fn):
    m = {}
    for x in l:
        k = fn(x)
        m.setdefault(k,[])
        m[k].append(x)
    return m

def get_leaderboard_records(all_runs):
    all_runs.sort(key = lambda x: x["date"])
    record = None
    cnt = 0
    weighted_cnt = 0

    for run in all_runs:
        if not record:
            record = {"id": run["id"], "time": run["time"], "date": run["date"], "runner": run["runner"]}
            cnt = 0
            weighted_cnt = 0
        elif run["time"] <= record["time"]:
            yield {"id": run["id"], "time": record["time"], "date": record["date"], "runner": record["runner"], "cnt": cnt, "weighted_cnt": weighted_cnt, "cur": 0}
            record = {"id": run["id"], "time": run["time"], "date": run["date"], "runner": run["runner"]}
            cnt = 0
            weighted_cnt = 0
        cnt += 1
        weighted_cnt += record["time"]
    if record:
        yield {"id": run["id"], "time": record["time"], "date": record["date"], "runner": record["runner"], "cnt": cnt, "weighted_cnt": weighted_cnt, "cur": 1}


if __name__ == "__main__":
    record_writer = csv.DictWriter(open("/tmp/records.csv","w"), fieldnames=["game", "category", "subcategory", "cnt", "weighted_cnt", "id", "time", "date", "runner", "cur"]) #sys.stdout
    record_writer.writeheader()


    r = requests.get("https://www.speedrun.com/_next/data/XLgRjmXwhBG4to23rTSTz/en-US/games.json?page=1&platform=&sort=mostruns")
    #print(r.text)
    top_games = json.loads(r.text)["pageProps"]["mainGames"]["gameList"]
    for game in top_games:
        #print(game)
        print("----")
        print("----")
        print("----")
        print("game")
        print(game["url"])
        #if game["url"] not in ["mcce"]: continue #"sm64","smo","sms","smb1","celeste","goiwbf"]: continue
        print(game["id"])
        #print(game)

        time_var = "igt" if game["igt"] else "time"

        print(f'{BASE_PATH}/v1/games/{game["id"]}/categories')

        r = requests.get(f'{BASE_PATH}/v1/games/{game["id"]}/categories')
        categories = json.loads(r.text)["data"]
        for category in categories:
            print(category)
            print(category["id"])
            r = requests.get(f'{BASE_PATH}/v1/categories/{category["id"]}/variables')
            variables = json.loads(r.text)["data"]
            variable_mapping = {}
            value_mapping = {}
            for var in variables:
                variable_mapping[var["id"]] = var["name"]
                for value in var["values"]["values"]:
                    value_mapping[value] = {
                        "value_id": value,
                        "value_name": var["values"]["values"][value]["label"],
                        "variable_id": var["id"],
                        "variable_name": var["name"],
                        "is_subcategory": var["is-subcategory"]
                    }

            params = {
                "categoryId": category["id"],
                "emulator": 1,
                "gameId": game["id"],
                "obsolete": 1,
                "platformIds": [],
                "regionIds": [],
                "timer": 0,
                "verified": 1,
                "values": [],
                "video": 0
            }

            runs = get_all_leaderboard_runs(params)
            all_run_info = []
            for run in runs:
                if not run["date"]: continue
                if not run.get(time_var): continue
                print(run)

                info = {
                    "id": run["id"],
                    "time": run[time_var],
                    "date": run["date"],
                    "runner": ",".join(run["playerIds"]),
                    "category": category["name"],
                    "subcategory": ",".join([f"{value_mapping[v]['variable_name']}:{value_mapping[v]['value_name']}" for v in run["valueIds"] if value_mapping[v]["is_subcategory"]] + (["levelId:"+run["levelId"]] if run.get("levelId") else []))
                }
                all_run_info.append(info)
            groups = group_by(all_run_info,lambda x: f'{x["category"]},{x["subcategory"]}')
            for k in groups:
                for r in get_leaderboard_records(groups[k]):
                    r["game"] = game["url"]
                    r["category"] = category["name"]
                    r["subcategory"] = k
                    record_writer.writerow(r)
            #raise
