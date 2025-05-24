import requests
import json
import time
from bs4 import BeautifulSoup
import csv
import sys
import re
import itertools
import datetime
import base64

#scrape speedrun.com to find the best records as measured by
#most runs submitted in that category before the record was broken

#NOTE: speedrun.com has an api but the api lumps together many
#leaderboards that show up separately on the speedrun.com website
#so scraping the website directly. Different games have different
#formats but this works on all games with 500+ runs as of 2020-10-18

#2021-09-25: trying to view all runs for the most popular games takes
#over 60 seconds -> gives a timeout. Not sure what to do, maybe check
#back in a month or two to see if it's fixed?

#2021-10-16: above error seems to be fixed, also

BASE_URL="https://speedrun.com/api/v1"

def get(url, options=None):
    delay = 1
    while True:
        try:
            return requests.get(url, options)
        except:
            time.sleep(delay)
            delay *= 1.25
            if delay > 60:
                raise

def get_most_popular_games():
    offset = 0;
    while True:
        r = get(f"https://www.speedrun.com/ajax_games.php?game=&platform=&unofficial=off&orderby=mostruns&title=&series=&start={offset}")
        soup = BeautifulSoup(r.text,"lxml")
        for game in soup.select("div.listcell > a"):
            abbreviation = game["href"]
            if abbreviation[0] != "/":
                raise
            abbreviation = abbreviation[1:]

            retries = 0
            while True:
                r = requests.get(f"{BASE_URL}/games", {'abbreviation': abbreviation})
                if json.loads(r.text).get("status",None) == 420:
                    retries += 1
                    continue
                if retries >= 3: raise
                data = json.loads(r.text)["data"]
                break
            if len(data) != 1: raise
            game_id = data[0]["id"]
            print({"abbreviation": abbreviation, "id": game_id})
            yield {"abbreviation": abbreviation, "id": game_id}
        offset += 50

def get_related_leaderboard_records(subcategory_to_runs, subcategory_to_slower):
    #function to handle the case where one platform is slower
    #than another but often (generally?) has faster runs

    #generate reverse map from subcategory to faster
    subcategory_to_faster = {}
    for faster in subcategory_to_slower:
        for slower in subcategory_to_slower[faster]:
            subcategory_to_faster[slower] = subcategory_to_faster.get(slower,[]) + [faster]

    all_runs = [{**run, "subcategory":subcategory} for subcategory in subcategory_to_runs for run in subcategory_to_runs[subcategory]]
    all_runs.sort(key = lambda x: x["date"])

    #only store records that are "active" ie not superceded by slower subcategories
    #so if the current best in the faster emulator subcategory is beaten by the slower N64
    #subcategory then wipe the emulator record entirely
    subcategory_records = {}
    subcategory_cnts = {}

    for run in all_runs:
        subcategory = run["subcategory"]
        slower_subcategories = subcategory_to_slower.get(subcategory,[])
        faster_subcategories = subcategory_to_faster.get(subcategory,[])
        #check if we beat a faster subcategory, if so wipe that subcategory's record entirely
        for faster in faster_subcategories:
            if faster in subcategory_records and run["time"] <= subcategory_records[faster]["time"]:
                yield {
                    "subcategory": faster,
                    "time": subcategory_records[faster]["time"],
                    "date": subcategory_records[faster]["date"],
                    "runner": subcategory_records[faster]["runner"],
                    "cnt":  subcategory_cnts[faster],
                    "cur":  0
                }
                del subcategory_records[faster]
                del subcategory_cnts[faster]

        #check if record for this subcategory (must be faster than slower subcategories too)
        same_or_slower_subcategory_records = [subcategory_records[x] for x in [subcategory] + slower_subcategories if x in subcategory_records]
        if all(run["time"] < record["time"] for record in same_or_slower_subcategory_records):
            if subcategory in subcategory_records:
                yield {
                    "subcategory": subcategory,
                    "time": subcategory_records[subcategory]["time"],
                    "date": subcategory_records[subcategory]["date"],
                    "runner": subcategory_records[subcategory]["runner"],
                    "cnt":  subcategory_cnts[subcategory],
                    "cur":  0
                }
            subcategory_records[subcategory] = {
                "time": run["time"],
                "date": run["date"],
                "runner": run["runner"]
            }
            subcategory_cnts[subcategory] = 0

        if subcategory in subcategory_cnts:
            #increment cnts for this subcategory and slower subcategories (if we didn't beat their record)
            subcategory_cnts[subcategory] += 1
        for slower in slower_subcategories:
            if slower in subcategory_records and subcategory_records[slower]["time"] < run["time"]:
                subcategory_cnts[slower] += 1
    #current records
    for subcategory in subcategory_records:
        yield {
            "runner": subcategory_records[subcategory]["runner"],
            "subcategory": subcategory,
            "time": subcategory_records[subcategory]["time"],
            "date": subcategory_records[subcategory]["date"],
            "runner": subcategory_records[subcategory]["runner"],
            "cnt":  subcategory_cnts[subcategory],
            "cur": 1
        }


def get_leaderboard_runs(url_params):
    print(url_params)
    r = get("https://www.speedrun.com/ajax_leaderboard.php",url_params)
    soup = BeautifulSoup(r.text,'lxml')

    time_col = None

    if soup.select("div.center") and soup.select("div.center")[0].text == "There are no runs.":
        return

    #find time column
    for i,x in enumerate(soup.select("th")):
        # print("header")
        # print(x)
        if x.text.lower() == "time":
            time_col = i
            break
        elif "time" in x.text.lower():
            onclick = x.select("a")[0]["onclick"]
            #example onclick: $('#loadtimes').val(0);
            var, val = re.findall("\$\('#(\w+)'\)\.val\((\d+)\);",onclick)[0]
            if url_params.get(var,None) == val:
                time_col = i
                break
            elif time_col is None:
                time_col = i

    if time_col is None:
        print(url_params)
        print(soup.select("th"))
        raise

    for i,result in enumerate(soup.select("tr.linked")):
        run = result["data-target"]
        cells = result.findAll("td")

        runner_cells = result.select("a.link-username")
        runner = re.sub("^/user/","",runner_cells[0]["href"]) if runner_cells else "Unknown"

        #time info stored in <small> tags
        time_cell = cells[time_col]
        if i==0 and not time_cell.text: #must find time_cell info in the first row
            #eg rocket league categories have only one run and that run doesn't have proper time info...
            skips = [
                {'timeunits': '0', 'topn': '-1', 'game': 'rocketleague', 'layout': 'new', 'verified': '1', 'loadtimes': '0', 'variable57717': '201201', 'variable57719': '201207', 'variable57718': '201205', 'obsolete': '1', 'category': '137726'},
                {'timeunits': '0', 'topn': '-1', 'game': 'robot64', 'layout': 'new', 'verified': '1', 'loadtimes': '2', 'variable22360': '175107', 'obsolete': '1', 'category': '68269'},
                {'timeunits': '0', 'topn': '-1', 'game': 'robot64', 'layout': 'new', 'verified': '1', 'loadtimes': '2', 'variable22360': '175108', 'obsolete': '1', 'category': '68269'},
                {'timeunits': '0', 'topn': '-1', 'game': 'robot64', 'layout': 'new', 'verified': '1', 'loadtimes': '2', 'variable31420': '105926', 'obsolete': '1', 'category': '89348'}
            ]
            if any([[i for i in x.items() if i[0] != 'vary'] <= [i for i in url_params.items() if i[0] != 'vary'] for x in skips]):
                continue
            raise Exception("Error, probably fix by adding url_params to the skips variable above")
        elif not time_cell.text:
            continue
        time_conversions = {"h": 3600, "m": 60, "s": 1, "ms": 0.001}
        convert_time = lambda x: time_conversions[re.sub("\d+","",x)] * float(re.findall("\d+",x)[0])
        time = sum([convert_time(x) for x in time_cell.text.split()])
        try:
            date = result.findAll("time")[0]["datetime"]
        except:
            continue #to time info

        if time == 0:
            if url_params["category"] == "119905": continue #google solitaire actually has a 0 second run?
            print(result)
            raise
        yield {"time":time, "date":date, "runner": runner, "info": run}


def get_leaderboard_records(all_runs):
    record = None
    cnt = 0

    for run in all_runs:
        if not record:
            record = {"time": run["time"], "date": run["date"], "runner": run["playerIds"][0]}
            cnt = 0
        elif run["time"] <= record["time"]:
            yield {"time": record["time"], "date": record["date"], "runner": record["runner"], "cnt": cnt, "cur": 0}
            record = {"time": run["time"], "date": run["date"], "runner": run["playerIds"][0]}
            cnt = 0
        cnt += 1
    if record:
        yield {"time": record["time"], "date": record["date"], "runner": record["runner"], "cnt": cnt, "cur": 1}

def get_multi_pbs(all_runs):
    #times when one player had multiple pbs above second place
    record_holder_runs = []
    runner_up_run = None

    for run in all_runs:
        if not record_holder_runs or run["time"] < record_holder_runs[-1]["time"]: #note: tying the record doesn't make you a new record holder
            #new record
            if not record_holder_runs or run["runner"] == record_holder_runs[-1]["runner"]:
                record_holder_runs.append({"time": run["time"], "date": run["date"], "runner": run["runner"]})
            else:
                record_holder_runs = [{"time": run["time"], "date": run["date"], "runner": run["runner"]}]
                runner_up_run = record_holder_runs[-1]
            yield {**record_holder_runs[-1], **{"is_record": 1, "record_runner": record_holder_runs[-1]["runner"], "record_runner_cnt": len(record_holder_runs)}}
        elif not runner_up_run or run["time"] < runner_up_run["time"]:
            if run["runner"] == record_holder_runs[-1]["runner"]:
                #shouldn't get here -- world record holder submitted a non-pb? Not really sure what to do, maybe this is an error
                continue
            else:
                #new runner up
                record_holder_runs = [x for x in record_holder_runs if x["time"] <= run["time"]] #note: ties go to the first runner
                runner_up_run = {"time": run["time"], "date": run["date"], "runner": run["runner"]}
                yield {**runner_up_run, **{"is_record": 0, "record_runner": record_holder_runs[-1]["runner"], "record_runner_cnt": len(record_holder_runs)}}


def get_leaderboards(game_info, writers):
    game_id = game_info["id"]
    time = int(datetime.datetime.utcnow().timestamp())

    def to_querystring(info):
        return base64.b64encode(bytes(json.dumps(info).replace(" ",""),"ascii")).decode("ascii").replace("=","")


    #info = {"params":{"gameId":"o1y9wo6q","categoryId":"n2y55mko","values":[],"timer":0,"regionIds":[],"platformIds":[],"emulator":1,"video":0,"obsolete":1},"page":1,"vary":time}

    info = {"gameId": "o1y9wo6q"}

    r = get("https://www.speedrun.com/api/v2/GetGameData", {"_r": to_querystring(info)})

    categories = json.loads(r.text)["categories"]
    variables = json.loads(r.text)["variables"]
    values = json.loads(r.text)["values"]

    gamewideVariables = []
    categoryVariables = {}
    variableValues = {}

    for x in variables:
        if x["categoryScope"] == -1:
            gamewideVariables.append(x)
        else:
            categoryVariables.setdefault(x["categoryId"],[])
            categoryVariables[x["categoryId"]].append(x)

    for x in values:
        variableValues.setdefault(x["variableId"],[])
        variableValues[x["variableId"]].append(x)

    print(categories)
    print(gamewideVariables)
    print(categoryVariables)
    print(variableValues)

    for cat in categories:
        values = []
        for var in gamewideVariables:
            if var["isSubcategory"]:
                pass

    info = {"params":{"gameId":"o1y9wo6q","categoryId":"n2y55mko","values":[{"variableId":"e8m7em86","valueIds":["9qj7z0oq"]}],"timer":0,"regionIds":[],"platformIds":[],"emulator":1,"video":0,"obsolete":1},"page":1,"vary":time}

    r = get("https://www.speedrun.com/api/v2/GetGameLeaderboard", {"_r": to_querystring(info)})
    page_cnt = json.loads(r.text)["leaderboard"]["pagination"]["pages"]
    print(page_cnt)

    runs = []
    for i in range(2): #page_cnt):
        info["page"] = i+1
        print("pulling page " + str(info["page"]))
        r = get("https://www.speedrun.com/api/v2/GetGameLeaderboard", {"_r": to_querystring(info)})
        if i+1 == 10:
            print(to_querystring(info))
        runs = runs + json.loads(r.text)["leaderboard"]["runs"]

    runs.sort(key=lambda x: x["date"])
    print(list(get_leaderboard_records(runs)))
    raise


    r = get(f"https://www.speedrun.com/{game_abbrev}")
    soup = BeautifulSoup(r.text,'lxml')
    categories = [{"name":x.text.strip(),"id":x["id"].replace("category","")} for x in soup.select("a.category")]

    print(game_abbrev)
    print(categories)
    raise

    #populate all_filters
    all_filters = []
    print(soup)
    for x in soup.select("div[data-cat]"):
        names = []
        for child in x.findAll(recursive=False): #add children names in order
            #pull dropdown buttons - add if this node matches "a.dropdown-item[onclick]" or contains nodes that do
            if child.name == "a" and "dropdown-item" in child.attrs['class'] and "onclick" in child.attrs:
                names += [child.text.strip()]
            names += [dropdown.text.strip() for dropdown in child.select("a.dropdown-item[onclick]")]
            #pull buttons - add if this node matches "label[for] contains nodes that do
            if child.name == "label" and "for" in child.attrs:
                names += [child.text.strip()]
            names += [button.text.strip() for button in child.select("label[for]")]

        if len(x.select("input")) != len(names):
            print("mismatch:")
            print(x)
            print(names)

        options = [{"variable": input_["name"], "value": input_["value"], "name": name if name else ""} for input_, name in itertools.zip_longest(x.select("input"), names)]
        all_filters.append({"category": x["data-cat"], "options": options})

    all_fields = soup.select('form input[value][type="hidden"]') #hidden form fields specify values

    for c in categories:
        print("category: ",c)
        #if c["id"] != "137726": continue
        subcategory_to_runs = get_subcategory_to_runs(game_abbrev, c, all_filters, all_fields)

        record_generator = get_sm64_records if game_abbrev == "sm64" else get_records
        for record in record_generator(game_abbrev, c, subcategory_to_runs):
            writers["records"].writerow(record)
        #TODO: update the below to handle sm64
        for subcat in subcategory_to_runs:
            runs = subcategory_to_runs[subcat]
            for multi_record in get_multi_pbs(runs):
                multi_record["category"] = c["name"]
                multi_record["subcategory"] = subcat
                multi_record["game"] = game_abbrev
                writers["multi_pb"].writerow(multi_record)

def get_sm64_records(game_abbrev, category, subcategory_to_runs):
    #for sm64 process the N64, VC and EMU categories at once:
    #VC and EMU are technically faster, but serious players
    #run N64 and those records are almost always fastest
    #so when a new player logs a slow EMU time that should count
    #towards the N64 record
    #only store a separate EMU/VC record in the rare case where EMU/VC
    #record is faster than the N64 record, and in that case new
    #slow EMU/VC runs count towards both the EMU/VC and N64 record

    subcategory_to_slower = {
        "VC": ["N64"],
        "EMU": ["N64"]
    }
    for r in get_related_leaderboard_records(subcategory_to_runs, subcategory_to_slower):
        r["game"] = game_abbrev
        r["category"] = category["name"]
        yield r


def get_records(game_abbrev, category, subcategory_to_runs):
    for subcategory in subcategory_to_runs:
        for r in get_leaderboard_records(subcategory_to_runs[subcategory]):
            r["game"] = game_abbrev
            r["category"] = category["name"]
            r["subcategory"] = subcategory
            yield r


def get_subcategory_to_runs(game_abbrev, category, all_filters, all_fields):
    relevant_filters = [f for f in all_filters if f["category"] in ["-1",category["id"]]]
    if game_abbrev == "sm64":
        #As of 2020-10-19 all subcategories are separated only by a single filter
        #on N64, VC and EMU: error if this changes
        #because the get_sm64_records() function will need to change
        if not (len(relevant_filters) == 1 and len(relevant_filters[0]["options"]) == 3):
            raise
    subcategory_runs = {}
    for filter_tuple in itertools.product(*[x["options"] for x in relevant_filters]):
        params = {}
        for f in all_fields:
            if f.get("name","") and f.get("value",""):
                if f["name"] == "category": continue #specifies the default category
                params[f["name"]] = f["value"]
        for x in filter_tuple:
            params[x["variable"]] = x["value"]
        params["topn"] = "-1" #new on 2021-09-25, website uses topn=1000
        params["obsolete"] = "1"
        params["category"] = category["id"]
        runs = list(get_leaderboard_runs(params))
        runs.sort(key = lambda x: x["date"])
        subcategory_runs["|".join([x["name"] for x in filter_tuple])] = runs
    return subcategory_runs

#NOTE: not using the api because it lumps together different leaderboards
def get_categories_from_api(game_id):
    r = get(f"{BASE_URL}/games/{game_id}/categories", {'max': 50})
    categories = {}
    for c in json.loads(r.text)["data"]:
        yield {"name": c["name"], "id": c["id"]}
    if len(categories) == 50:
        raise Exception("more than 50 categories")

def get_records_from_api(category_id = None):
    data = {}
    if category_id:
        data['category'] = category_id

    data["orderby"] = "date" #"submitted"
    data["offset"] = 0
    data["max"] = 200

    output = "/tmp/runs.txt"

    record = None
    cnt = 0

    while True:
        time.sleep(1) #api rate limit is 100 / minute
        r = get(f"{BASE_URL}/runs", data)
        if not json.loads(r.text)["data"]: break
        for r in json.loads(r.text)["data"]:
            #if r["submitted"] == None: continue
            if r["status"]["status"] != "verified": continue
            runtime = r["times"]["primary_t"]
            if not record:
                record = {"time": runtime, "date":r["date"]}
                cnt = 0
            elif runtime <= record["time"]:
                yield {"time":record["time"], "date":record["date"], "cnt":cnt, "cur":0}
                record = {"time":runtime, "date":r["date"]}
                cnt = 0
            cnt += 1
        data["offset"] += data["max"]
    yield {"time":record["time"], "date":record["date"], "cnt":cnt, "cur":1}

if __name__ == "__main__":
    #setup csv writers
    record_writer = csv.DictWriter(open("/tmp/records.csv","w"), fieldnames=["game", "category", "subcategory", "cnt", "time", "date", "runner", "cur"]) #sys.stdout
    record_writer.writeheader()

    multi_pb_writer = csv.DictWriter(open("/tmp/multipb.csv","w"), fieldnames=["game", "category", "subcategory", "time", "date", "runner", "is_record", "record_runner", "record_runner_cnt"])
    multi_pb_writer.writeheader()


    csv_writers = {
        "records": record_writer,
        "multi_pb": multi_pb_writer
    }

    #game = "rocketleague"
    game = None
    start = False
    for g in get_most_popular_games():
        #if g["abbreviation"] == "stardew_valley": break
        if game is not None:
            if g["abbreviation"] == game:
                start = True
            if start:
                get_leaderboards(g, csv_writers)
        else:
            get_leaderboards(g, csv_writers)
