var resemble = require('./node_modules/node-resemble-js/resemble.js');
var fs = require('fs');

var args = process.argv.slice(2);
if (args.length != 3) {
    console.log("Usage: compare.js image1 image2 resultimage.jpg");
    return;
}

resemble(args[0]).compareTo(args[1]).onComplete(function (data) {
    fs.writeFileSync(args[2], data.getDiffImageAsJPEG());
    var result = (100 - data.misMatchPercentage) / 100;
    console.log(result);
});