/*! Select2 4.1.0-rc.0 | https://github.com/select2/select2/blob/master/LICENSE.md */
var dalLoadLanguage=function(n){var e;(e=n&&n.fn&&n.fn.select2&&n.fn.select2.amd?n.fn.select2.amd:e).define("select2/i18n/lt",[],function(){function e(n,e,t,i){return n%10==1&&(n%100<11||19<n%100)?e:2<=n%10&&n%10<=9&&(n%100<11||19<n%100)?t:i}return{inputTooLong:function(n){n=n.input.length-n.maximum;return"Pašalinkite "+n+" simbol"+e(n,"į","ius","ių")},inputTooShort:function(n){n=n.minimum-n.input.length;return"Įrašykite dar "+n+" simbol"+e(n,"į","ius","ių")},loadingMore:function(){return"Kraunama daugiau rezultatų…"},maximumSelected:function(n){return"Jūs galite pasirinkti tik "+n.maximum+" element"+e(n.maximum,"ą","us","ų")},noResults:function(){return"Atitikmenų nerasta"},searching:function(){return"Ieškoma…"},removeAllItems:function(){return"Pašalinti visus elementus"}}}),e.define,e.require},event=new CustomEvent("dal-language-loaded",{lang:"lt"});document.dispatchEvent(event);
