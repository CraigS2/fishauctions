/*! Select2 4.1.0-rc.0 | https://github.com/select2/select2/blob/master/LICENSE.md */
var dalLoadLanguage=function(n){var e;(e=n&&n.fn&&n.fn.select2&&n.fn.select2.amd?n.fn.select2.amd:e).define("select2/i18n/hsb",[],function(){function e(n,e){return 1===n?e[0]:2===n?e[1]:2<n&&n<=4?e[2]:5<=n?e[3]:void 0}var a=["znamješko","znamješce","znamješka","znamješkow"],t=["zapisk","zapiskaj","zapiski","zapiskow"];return{errorLoading:function(){return"Wuslědki njedachu so začitać."},inputTooLong:function(n){n=n.input.length-n.maximum;return"Prošu zhašej "+n+" "+e(n,a)},inputTooShort:function(n){n=n.minimum-n.input.length;return"Prošu zapodaj znajmjeńša "+n+" "+e(n,a)},loadingMore:function(){return"Dalše wuslědki so začitaja…"},maximumSelected:function(n){return"Móžeš jenož "+n.maximum+" "+e(n.maximum,t)+"wubrać"},noResults:function(){return"Žane wuslědki namakane"},searching:function(){return"Pyta so…"},removeAllItems:function(){return"Remove all items"}}}),e.define,e.require},event=new CustomEvent("dal-language-loaded",{lang:"hsb"});document.dispatchEvent(event);
