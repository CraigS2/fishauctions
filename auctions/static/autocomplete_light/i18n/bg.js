/*! Select2 4.1.0-rc.0 | https://github.com/select2/select2/blob/master/LICENSE.md */
var dalLoadLanguage=function(n){var e;(e=n&&n.fn&&n.fn.select2&&n.fn.select2.amd?n.fn.select2.amd:e).define("select2/i18n/bg",[],function(){return{inputTooLong:function(n){var e=n.input.length-n.maximum,n="Моля въведете с "+e+" по-малко символ";return 1<e&&(n+="a"),n},inputTooShort:function(n){var e=n.minimum-n.input.length,n="Моля въведете още "+e+" символ";return 1<e&&(n+="a"),n},loadingMore:function(){return"Зареждат се още…"},maximumSelected:function(n){var e="Можете да направите до "+n.maximum+" ";return 1<n.maximum?e+="избора":e+="избор",e},noResults:function(){return"Няма намерени съвпадения"},searching:function(){return"Търсене…"},removeAllItems:function(){return"Премахнете всички елементи"}}}),e.define,e.require},event=new CustomEvent("dal-language-loaded",{lang:"bg"});document.dispatchEvent(event);
