/*! Select2 4.1.0-rc.0 | https://github.com/select2/select2/blob/master/LICENSE.md */
var dalLoadLanguage=function(e){var n;(n=e&&e.fn&&e.fn.select2&&e.fn.select2.amd?e.fn.select2.amd:n).define("select2/i18n/sk",[],function(){var n={2:function(e){return e?"dva":"dve"},3:function(){return"tri"},4:function(){return"štyri"}};return{errorLoading:function(){return"Výsledky sa nepodarilo načítať."},inputTooLong:function(e){e=e.input.length-e.maximum;return 1==e?"Prosím, zadajte o jeden znak menej":2<=e&&e<=4?"Prosím, zadajte o "+n[e](!0)+" znaky menej":"Prosím, zadajte o "+e+" znakov menej"},inputTooShort:function(e){e=e.minimum-e.input.length;return 1==e?"Prosím, zadajte ešte jeden znak":e<=4?"Prosím, zadajte ešte ďalšie "+n[e](!0)+" znaky":"Prosím, zadajte ešte ďalších "+e+" znakov"},loadingMore:function(){return"Načítanie ďalších výsledkov…"},maximumSelected:function(e){return 1==e.maximum?"Môžete zvoliť len jednu položku":2<=e.maximum&&e.maximum<=4?"Môžete zvoliť najviac "+n[e.maximum](!1)+" položky":"Môžete zvoliť najviac "+e.maximum+" položiek"},noResults:function(){return"Nenašli sa žiadne položky"},searching:function(){return"Vyhľadávanie…"},removeAllItems:function(){return"Odstráňte všetky položky"}}}),n.define,n.require},event=new CustomEvent("dal-language-loaded",{lang:"sk"});document.dispatchEvent(event);
