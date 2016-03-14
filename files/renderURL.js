"use strict";

function usage(msg) {
    console.log('Usage: renderURL.js <URL> <output file> --viewport <viewport 1920x1920> --clip <clip geometry 600x800+10+10> --zoom <zoom 0.0~1.0> [--header "<header key>: <value>" ...]');
    console.log(msg);

    phantom.exit(1);
}

var system = require('system');

function parse_arguments(args_input) {
    var flags = {};
    var args = new Array();
    var found_flag = null;

    args_input.slice(1).forEach(function(i) {
        if (i.indexOf('--') < 0) { // this is flag
            if (found_flag) {
                if (found_flag == 'header') {
                    flags[found_flag].push(i);
                } else {
                    flags[found_flag] = i;
                }
                found_flag = null;
            } else {
                args.push(i);
            }
        } else {
            var flag = i.replace(/^\-\-/g, '');
            found_flag = flag;
            if (flag == 'header') {
                if (typeof flags[flag] == 'undefined') flags[flag] = new Array();
            } else {
                flags[flag] = null;
            }
        }
    });

    return {
        args: args,
        flags: flags
    };

}

var options = {
    url: null,
    output: null,
    viewport: { width: 600, height: 600 },
    clipRect: {width: null, height: null, top: null, left: null},
    zoom: 1.0,
    header: null
}

var parsed = parse_arguments(system.args);

options.url = parsed.args[0];
options.output = parsed.args[1];

if (typeof options.url == 'undefined') usage();
if (typeof options.output == 'undefined') usage();

// viewport
if (typeof parsed.flags.viewport != 'undefined') {
    try {
        var size = parsed.flags.viewport.split('x');
        options.viewport = {width: parseInt(size[0], 10), height: parseInt(size[1], 10)};

        if (! options.viewport.width || ! options.viewport.height ) {
            throw 'invalid viewport: `' + size + '`';
        }
    } catch(e) {
        usage(e);
    }
}

// clip
if (typeof parsed.flags.clip != 'undefined') {
    try {
        var geo = parsed.flags['clip'].split('+');
        if (geo.length > 0) {
            var r = geo[0].split('x').map(function(i) {
                return parseInt(i);
            });
            options.clipRect.width = r[0];
            options.clipRect.height = r[1];
        }
        if (geo.length > 1) options.clipRect.top = parseInt(geo[1]);
        if (geo.length > 2) options.clipRect.left = parseInt(geo[2]);

        if (! options.clipRect.width || ! options.clipRect.height) {
            throw 'invalid clip: `' + parsed.flags['clip'] + '`';
        }

        if ([options.clipRect.top, options.clipRect.left].indexOf(null) > -1) {
            throw 'invalid clip: `' + parsed.flags['clip'] + '`';
        }

    } catch (e) {
        usage(e);
    }
}

// zoom
if (typeof parsed.flags.zoom != 'undefined') {
    try {
        options.zoom = parseFloat(parsed.flags.zoom);
        if (! options.zoom || options.zoom < 0 || options.zoom > 1) {
            throw 'invalid zoom: `' + parsed.flags.zoom + '`';
        }
    } catch(e) {
        usage(e);
    }
}

// header
if (typeof parsed.flags.header != 'undefined' && parsed.flags.header.length > 0) {
    var headers = {};

    try {
        parsed.flags.header.forEach(function(i) {
            var hs = i.split(':').map(function(j) {
                return j.replace(/^[ ][ ]*/g, '').replace(/[ ][ ]*$/g, '');
            });
            if (hs.length != 2) throw 'invalid header: `' + i + '`';
            headers[hs[0]] = hs[1];

            return;
        });
    } catch (e) {
        usage(e);
    }

    options.headers = headers;
}

console.log('options:', JSON.stringify(options, null, 2));

var page = require('webpage').create();

page.viewportSize = options.viewport;
page.customHeaders = options.headers

page.clipRect = options.clipRect;
page.zoomFactor = options.zoom;

console.log('page.viewportSize:', JSON.stringify(page.viewportSize));
console.log('    page.clipRect:', JSON.stringify(page.clipRect));
console.log('    page.zoomFactor:', JSON.stringify(page.zoomFactor));

page.open(options.url, function (status) {
    if (status !== 'success') {
        console.log('[error] Unable to load the address, `' + address + '`!');
        phantom.exit(1);
    } else {
        window.setTimeout(function () {
            page.render(options.output);
			console.log('successfully rendered to `' + options.output + '`.');
            phantom.exit();
        }, 1000);
    }
});
