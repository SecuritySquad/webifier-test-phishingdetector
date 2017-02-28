"use strict";
var page = require('webpage').create(),
    system = require('system');

if (system.args.length === 1) {
    console.log('Usage: website.js <URL> keywordcount screenshot.png');
    phantom.exit(1);
} else {
    page.address = system.args[1];
    page.results = system.args[2];
    page.screenshot = system.args[3];
    page.onError = function (msg, trace) {
        return true;
    };

    page.settings.userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36';
    page.open(page.address, function (status) {
        if (status !== 'success') {
            console.log('FAIL to load the address');
            phantom.exit(1);
        } else {
            page.render(page.screenshot);
            var content = page.content.replace(/<style.*?>[\S\s]+<\/style>|<script.*?>[\S\s]+?<\/script>|<\/?[^>]+(>|$)|['".:,;()\[\]{}|=]/g, "");
            var words = content.match(/\S+/g);
            var dictionary = [];
            addWordsToDictionary(page.title.replace(/['".:,;()\[\]{}|]/g, "").split(" "), dictionary, 5);
            addWordsToDictionary(words, dictionary);
            var images = page.evaluate(function () {
                var elements = document.getElementsByTagName('img');
                var alts = [];
                for (var i = 0; i < elements.length; i++) {
                    alts.push(elements[i].alt);
                }
                return alts;
            });
            for (var i = 0; i < images.length; i++) {
                var image = images[i].replace(/[.:,;()\[\]{}]/g, "");
                addWordsToDictionary(image.split(" "), dictionary, 2);
            }

            var hs = page.evaluate(function () {
                var elements = document.getElementsByTagName('*');
                var elArray = [];
                var regex = new RegExp("H[1-6]");
                for (var i = 0; i < elements.length; i++) {
                    if (regex.test(elements[i].tagName)) {
                        elArray.push(elements[i].textContent);
                    }
                }
                return elArray;
            });
            for (var i = 0; i < hs.length; i++) {
                var h = hs[i].replace(/[.:,;()\[\]{}]/g, "");
                addWordsToDictionary(h.split(" "), dictionary);
            }

            var result = {
                "screenshot": page.screenshot,
                "html": page.content,
                "content": words.join(' '),
                "keywords": map(dictionary).slice(0, page.results)
            };

            console.log(JSON.stringify(result));

            phantom.exit();
        }
    });
}


function map(d) {
    var dictionary = [];

    for (var word in d) {
        var count = d[word];
        dictionary.push({
            name: word,
            count: count
        });
    }

    dictionary.sort(function (a, b) {
        var number = b.count - a.count;
        if (number != 0)
            return number;
        return b.name.length - a.name.length
    });

    return dictionary;
}

function addWordsToDictionary(words, dictionary, count) {
    var add = count | 1;
    for (var i = 0; i < words.length; i++) {
        var word = words[i].toLowerCase();
        if (word.length > 3)
            if (word in dictionary) {
                dictionary[word] += add;
            } else {
                dictionary[word] = 1;
            }
    }
}