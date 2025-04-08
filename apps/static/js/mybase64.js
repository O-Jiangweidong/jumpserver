var base64EncodeChars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
var base64DecodeChars = new Array(
    -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
    -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
    -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 62, -1, -1, -1, 63,
    52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -1, -1, -1, -1, -1, -1,
    -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
    15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, -1, -1, -1, -1,
    -1, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, -1, -1, -1, -1, -1);

function base64encode(str) {
    var out, i, len;
    var c1, c2, c3;

    len = str.length;
    i = 0;
    out = "";
    while (i < len) {
        c1 = str.charCodeAt(i++) & 0xff;
        if (i == len) {
            out += base64EncodeChars.charAt(c1 >> 2);
            out += base64EncodeChars.charAt((c1 & 0x3) << 4);
            out += "==";
            break;
        }
        c2 = str.charCodeAt(i++);
        if (i == len) {
            out += base64EncodeChars.charAt(c1 >> 2);
            out += base64EncodeChars.charAt(((c1 & 0x3) << 4) | ((c2 & 0xF0) >> 4));
            out += base64EncodeChars.charAt((c2 & 0xF) << 2);
            out += "=";
            break;
        }
        c3 = str.charCodeAt(i++);
        out += base64EncodeChars.charAt(c1 >> 2);
        out += base64EncodeChars.charAt(((c1 & 0x3) << 4) | ((c2 & 0xF0) >> 4));
        out += base64EncodeChars.charAt(((c2 & 0xF) << 2) | ((c3 & 0xC0) >> 6));
        out += base64EncodeChars.charAt(c3 & 0x3F);
    }
    return out;
}

function base64decode(str) {
    var c1, c2, c3, c4;
    var i, len, out;

    len = str.length;
    i = 0;
    out = "";
    while (i < len) {
        /* c1 */
        do {
            c1 = base64DecodeChars[str.charCodeAt(i++) & 0xff];
        } while (i < len && c1 == -1);
        if (c1 == -1)
            break;

        /* c2 */
        do {
            c2 = base64DecodeChars[str.charCodeAt(i++) & 0xff];
        } while (i < len && c2 == -1);
        if (c2 == -1)
            break;

        out += String.fromCharCode((c1 << 2) | ((c2 & 0x30) >> 4));

        /* c3 */
        do {
            c3 = str.charCodeAt(i++) & 0xff;
            //console.log("c3:"+c3);
            if (c3 == 61)
                // console.log("222:"+out);
                return out;
            c3 = base64DecodeChars[c3];
        } while (i < len && c3 == -1);
        if (c3 == -1)
            break;

        out += String.fromCharCode(((c2 & 0XF) << 4) | ((c3 & 0x3C) >> 2));

        /* c4 */
        do {
            c4 = str.charCodeAt(i++) & 0xff;
            //console.log("c4:"+c4);
            if (c4 == 61)
                // console.log("333:"+out);
                return out;
            c4 = base64DecodeChars[c4];
        } while (i < len && c4 == -1);
        if (c4 == -1)
            break;
        out += String.fromCharCode(((c3 & 0x03) << 6) | c4);
    }

    // console.log("111:"+out);
    return out;
}

function utf16to8(str) {
    var out, i, len, c;

    out = "";
    len = str.length;
    for (i = 0; i < len; i++) {
        c = str.charCodeAt(i);
        if ((c >= 0x0001) && (c <= 0x007F)) {
            out += str.charAt(i);
        } else if (c > 0x07FF) {
            out += String.fromCharCode(0xE0 | ((c >> 12) & 0x0F));
            out += String.fromCharCode(0x80 | ((c >> 6) & 0x3F));
            out += String.fromCharCode(0x80 | ((c >> 0) & 0x3F));
        } else {
            out += String.fromCharCode(0xC0 | ((c >> 6) & 0x1F));
            out += String.fromCharCode(0x80 | ((c >> 0) & 0x3F));
        }
    }
    return out;
}

function utf8to16(str) {
    var out, i, len, c;
    var char2, char3;

    out = "";
    len = str.length;
    i = 0;
    while (i < len) {
        c = str.charCodeAt(i++);
        switch (c >> 4) {
            case 0:
            case 1:
            case 2:
            case 3:
            case 4:
            case 5:
            case 6:
            case 7:
                // 0xxxxxxx
                out += str.charAt(i - 1);
                break;
            case 12:
            case 13:
                // 110x xxxx   10xx xxxx
                char2 = str.charCodeAt(i++);
                out += String.fromCharCode(((c & 0x1F) << 6) | (char2 & 0x3F));
                break;
            case 14:
                // 1110 xxxx  10xx xxxx  10xx xxxx
                char2 = str.charCodeAt(i++);
                char3 = str.charCodeAt(i++);
                out += String.fromCharCode(((c & 0x0F) << 12) |
                    ((char2 & 0x3F) << 6) |
                    ((char3 & 0x3F) << 0));
                break;
        }
    }

    return out;
}

function CharToHex(str) {
    var out, i, h;
    out = "";
    i = 0;
    while (i < str.length) {
        h = str.charCodeAt(i++).toString(16);
        out += "\\0x" + h;
        out += (i > 0 && i % 8 == 0) ? "\r\n" : ", ";
    }
    return out;
}

function CharToHexStr(str) {
    var out, i, h;
    out = "";
    i = 0;
    while (i < str.length) {
        h = str.charCodeAt(i++).toString(16);
        // console.log("h::"+h+"-"+h.length);
        if (h.length == 1) {
            var nh = "0" + h;
            out += nh;
            continue;
        }
        // console.log("h2::"+h+"-"+h.length);
        out += h;
        //out += "\\0x" + h;
        //out +=(i > 0 && i % 8 == 0)?"\r\n":", ";
    }
    return out.toUpperCase();
}

function StrPadding0(str) {
    var out, i, h;
    out = "";
    i = 0;
    while (i < str.length) {
        h = str.charCodeAt(i++).toString(16);
        if (h.length == 1) {
            //out+="0"+h;
        }
        out += h;
        //out += "\\0x" + h;
        //out +=(i > 0 && i % 8 == 0)?"\r\n":", ";
    }
    return out.toUpperCase();
}

function ac_doEncode() {
    var src = document.getElementById('src').value;
    var opts = document.getElementById('opt1');
    document.getElementById('dest').value = opts.checked ? CharToHex(base64encode(utf16to8(src))) : base64encode(utf16to8(src));
}

function ac_doEncode(val) {
    var result = CharToHexStr(base64encode(utf16to8(val)));
    //var result = base64encode(utf16to8(val));
    return result;
    // var src = document.getElementById('src').value;
    // var opts = document.getElementById('opt1');
    // document.getElementById('dest').value = opts.checked?CharToHex(base64encode(utf16to8(src))):base64encode(utf16to8(src));
}

function ac_doDecode() {
    var src = document.getElementById('src').value;
    var opts = document.getElementById('opt2');
    document.getElementById('dest').value = opts.checked ? CharToHex(base64decode(src)) : utf8to16(base64decode(src));
}

function ac_doDecode(val) {
    // var aa = base64decode(val);
    // console.log("aa:"+aa);
    var result = CharToHexStr(base64decode(val));
    return result;
}

var tableStr = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
var table = tableStr.split("");

window.atob = function (base64) {
    if (/(=[^=]+|={3,})$/.test(base64)) throw new Error("String contains an invalid character");
    base64 = base64.replace(/=/g, "");
    var n = base64.length & 3;
    if (n === 1) throw new Error("String contains an invalid character");
    for (var i = 0, j = 0, len = base64.length / 4, bin = []; i < len; ++i) {
        var a = tableStr.indexOf(base64[j++] || "A"), b = tableStr.indexOf(base64[j++] || "A");
        var c = tableStr.indexOf(base64[j++] || "A"), d = tableStr.indexOf(base64[j++] || "A");
        if ((a | b | c | d) < 0) throw new Error("String contains an invalid character");
        bin[bin.length] = ((a << 2) | (b >> 4)) & 255;
        bin[bin.length] = ((b << 4) | (c >> 2)) & 255;
        bin[bin.length] = ((c << 6) | d) & 255;
    }
    ;
    return String.fromCharCode.apply(null, bin).substr(0, bin.length + n - 4);
};

window.btoa = function (bin) {
    for (var i = 0, j = 0, len = bin.length / 3, base64 = []; i < len; ++i) {
        var a = bin.charCodeAt(j++), b = bin.charCodeAt(j++), c = bin.charCodeAt(j++);
        if ((a | b | c) > 255) throw new Error("String contains an invalid character");
        base64[base64.length] = table[a >> 2] + table[((a << 4) & 63) | (b >> 4)] +
            (isNaN(b) ? "=" : table[((b << 2) & 63) | (c >> 6)]) +
            (isNaN(b + c) ? "=" : table[c & 63]);
    }
    return base64.join("");
};


function hexToBase64(str) {
    return btoa(String.fromCharCode.apply(null,
        str.replace(/\r|\n/g, "").replace(/([\da-fA-F]{2}) ?/g, "0x$1 ").replace(/ +$/, "").split(" "))
    );
}

function base64ToHex(str) {
    for (var i = 0, bin = atob(str.replace(/[ \r\n]+$/, "")), hex = []; i < bin.length; ++i) {
        var tmp = bin.charCodeAt(i).toString(16);
        if (tmp.length === 1) tmp = "0" + tmp;
        hex[hex.length] = tmp;
    }
    return hex.join("");
}

