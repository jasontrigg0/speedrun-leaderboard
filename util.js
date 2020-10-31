const parse = require('csv-parse');
const stringify = require('csv-stringify');
const readline = require('readline');
fs = require('fs');

async function* readCsvFiles(infileList) {
  for (let infile of infileList) {
    let rowList = await readCsv(infile);
    for (let row of rowList) {
      yield row;
    }
  }
}

async function readCsv(infile = undefined) {
  return new Promise((res, rej) => {
    const output = [];

    //https://csv.js.org/parse/api/
    // Create the parser
    const parser = parse({
      columns:true
    });
    // Use the readable stream api
    parser.on('readable', function(){
      let record
      while (record = parser.read()) {
        output.push(record)
      }
    });
    // Catch any error
    parser.on('error', function(err){
      console.error(err.message)
    });
    // When we are done, test that the parsed output matched what expected
    parser.on('end', function(){
      res(output);
    });

    //read stdin line by line: https://stackoverflow.com/a/20087094/10859403
    var rl = readline.createInterface({
      input: infile ? fs.createReadStream(infile) : process.stdin,
      output: process.stdout,
      terminal: false
    });

    rl.on('line', function(line) {
      parser.write(line + '\n');
    }).on('close', () => {
      parser.end();
    });
  });
}

function writeCsv(rows, outfile = undefined) {
  const outstream = outfile ? fs.createWriteStream(outfile) : process.stdout;

  //https://csv.js.org/stringify/api/
  stringify( rows, {
    header: true,
    columns: Object.keys(rows[0]).map(x => ({key: x}))
  }, function(err, data){
    outstream.write(data);
  })

  //TODO: write from streams: https://csv.js.org/stringify/api/
}

function sortArray(arr, key = undefined, cmpTuples = false) {
  //cmpTuples=true to sort an array of tuples
  //as python would, ie element by element
  //[1,2] < [1,4] < [2,-10] < [2,0] < [3,-1] etc.
  const basicCmpFn = (a,b) => a > b ? 1 : (a < b ? -1 : 0);
  const cmpTuplesFn = (a,b) => {
    if (a.length !== b.length) {
      throw new Error('Sorting unequal sized tuples');
    }
    let out = 0;
    for (let i=0; i<a.length; i++) {
      out = out || basicCmpFn(a[i],b[i]);
    }
    return out;
  };

  let keyFn = key || ((x) => x);
  let cmpFn = cmpTuples ? cmpTuplesFn : basicCmpFn;
  arr.sort((a,b) => cmpFn(keyFn(a),keyFn(b)));
}

function dedupListOfObjects(list) {
  list = list.map(x => JSON.stringify(x));
  list = [...new Set(list)];
  return list.map(x => JSON.parse(x));
}

exports.readCsv = readCsv;
exports.readCsvFiles = readCsvFiles;
exports.writeCsv = writeCsv;
exports.sortArray = sortArray;
exports.dedupListOfObjects = dedupListOfObjects;