/*! Select2 4.1.0-rc.0 | https://github.com/select2/select2/blob/master/LICENSE.md */
var dalLoadLanguage=function(n){var e;(e=n&&n.fn&&n.fn.select2&&n.fn.select2.amd?n.fn.select2.amd:e).define("select2/i18n/te",[],function(){return{errorLoading:function(){return"ఫలితాలు చూపించలేకపోతున్నాము"},inputTooLong:function(n){n=n.input.length-n.maximum;return n+(1!=n?" అక్షరాలు తొలిగించండి":" అక్షరం తొలిగించండి")},inputTooShort:function(n){return n.minimum-n.input.length+" లేక మరిన్ని అక్షరాలను జోడించండి"},loadingMore:function(){return"మరిన్ని ఫలితాలు…"},maximumSelected:function(n){var e="మీరు "+n.maximum;return 1!=n.maximum?e+=" అంశాల్ని మాత్రమే ఎంచుకోగలరు":e+=" అంశాన్ని మాత్రమే ఎంచుకోగలరు",e},noResults:function(){return"ఫలితాలు లేవు"},searching:function(){return"శోధిస్తున్నాము…"},removeAllItems:function(){return"అన్ని అంశాల్ని తొలిగించండి"},removeItem:function(){return"తొలిగించు"}}}),e.define,e.require},event=new CustomEvent("dal-language-loaded",{lang:"te"});document.dispatchEvent(event);
