const { sortArray,readCsvFiles } = require("./util.js");
const { gameInfo } = require("./games.js");
moment = require('moment');
fs = require('fs');

function generateHtml(info) {
  let headerHtml = '<h2 style="padding-top: 10px; text-align: center">Top speedrun records</h2><div style="text-align: center">Measured by number of runs submitted to speedrun.com in that category before the record was broken.</div>\n';

  let cardHtml = '';
  cardHtml += `<div style="margin-top: 40px; flex-direction: row; justify-content: space-around" class="tab-panel active">`;
  cardHtml += generateCards("Current", info.filter(x => x["cur"] === "1"));
  cardHtml += generateCards("All Time", info);
  cardHtml += '</div>';

  const HTML_HEADER = `
  <head>
    <!-- Required styles for MDC Web -->
    <link rel="stylesheet" href="https://unpkg.com/material-components-web@latest/dist/material-components-web.min.css">
    <link rel="stylesheet" href="mdc-demo-card.css">
    <link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
    <style>
     .tab-panel {
       display: none;
     }
     .tab-panel.active {
       display: flex;
     }
    </style>
  </head>
  <body>
  `;

  const HTML_FOOTER = `
    <!-- Required MDC Web JavaScript library -->
    <script src="https://unpkg.com/material-components-web@latest/dist/material-components-web.min.js"></script>
    <script>
     //setup tabs
     window.onload = function() {
       for (const e of document.querySelectorAll(".mdc-tab-bar")) {
         let tab = new mdc.tabBar.MDCTabBar(e)
         tab.preventDefaultOnClick = true

         tab.listen("MDCTabBar:activated", function({detail: {index: index}}) {
           // Hide all panels.
           for (const t of document.querySelectorAll(".tab-panel")) {
             t.classList.remove("active")
           }

           // Show the current one.
           let tab = document.querySelector(".tab-panel:nth-child(" + (index + 2) + ")")
           tab.classList.add("active")
         })
       }
     };
    </script>
  </body>
</html>
  `;

  return HTML_HEADER + headerHtml + cardHtml + HTML_FOOTER;
}

function generateCard(image, header1, header2, header3, header4) {
    return `
    <div class="mdc-card" style="margin-bottom: 20px; max-width: 500px;">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div style="display: flex; margin-left: 25px; height: 120px; width: 120px; justify-content: center; align-items: center">
          <img style="max-height: 120px" src="${image}"></img>
        </div>
        <div>
          <div class="demo-card__primary">
            <h2 style="text-align: right" class="demo-card__title mdc-typography mdc-typography--headline6">${header1}</h2>
            <h2 style="text-align: right" class="demo-card__title mdc-typography mdc-typography--headline6">${header2}</h2>
          </div>
          <div style="text-align: right; padding-bottom: 0" class="demo-card__secondary mdc-typography mdc-typography--body2">${header3}</div>
          <div style="text-align: right" class="demo-card__secondary mdc-typography mdc-typography--body2">${header4}</div>
        </div>
      </div>
    </div>`;
}

function generateCards(title, info) {
  let allCards = [];
  let cnt = 1;
  for (let row of info) {
    if (!gameInfo[row["game"]]) {
      console.log("game not found");
      console.log(row);
    }
    let cat = [row["category"], row["subcategory"]].filter(x => x).join(', ');
    let timeString = moment.utc(row["time"]*1000).format('HH:mm:ss.SSS').replace(/^0(?:0:0?)?:?/, '').replace(/\.000/,'');

    let card = generateCard(
      gameInfo[row["game"]]["image"],
      `#${cnt} ${row["runner"]}`,
      `${row["cnt"]} runs`,
      `${gameInfo[row["game"]]["name"]}: ${cat} in ${timeString}`,
      `${moment(row["date"]).format('LL')}`
    );
    allCards.push(card);
    cnt += 1;
    if (cnt > 25) break;
  }
  let html = "";
  let header = `<div style="text-align: center; padding-bottom: 10px">${title}</div>`;

  return `  <div style="max-width: 500px">` + header + allCards.join("\n") + "\n" + `  </div>`;
}


async function main() {
  //let info = await generateInfo(fs.readdirSync('game_data/nfl/').map(x => 'game_data/nfl/' + x), "0601");

  let info = [];
  for await (let row of readCsvFiles(['/tmp/records.csv'])) {
    if (row["game"] === "dragster") continue;
    if (row["game"] === "supermetroid" && row["category"] === "Ceres Escape") continue;
    info.push(row);
  }

  sortArray(info, key= x=> -1 * x["cnt"]);

  const html = generateHtml(info);

  fs.writeFile('index.html', html, function (err) {
    if (err) return console.log(err);
  });
}

main();
