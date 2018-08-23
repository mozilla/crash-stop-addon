/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

function getParams() {
    let params = ["channel", "product", "filter"].map(function(i) {
        let e = document.getElementById(i);
        return e.options[e.selectedIndex].value;
    });
    return params;
}

function update() {
    let params = getParams();
    location.href = "signatures.html?channel=" + params[0]
                  + "&product=" + params[1]
                  + "&filter=" + params[2];
}

function bug() {
    let bugid = document.getElementById("bugid").value;
    location.href = "bug.html?id=" + bugid;
}

function crashdata() {
    let data = ["signatures", "hgurls"].map(function(i) {
        return document.getElementById(i).value.split("\n").map(function(s) {
            return s.trim()
        }).filter(function(s) {
            return s;
        }).map(function(s) {
            return i + "=" + s
        }).join("&");
    });
    let prods = products.map(function(i) {
        return document.getElementById(i).checked ? i : "";
    }).filter(function(s) {
        return s;
    }).map(function(s) {
        return "products=" + s;
    }).join("&");

    location.href = "crashdata.html?" + data[0]
                  + "&" + data[1]
                  + "&" + prods;
}
