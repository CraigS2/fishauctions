/*! Select2 4.1.0-rc.0 | https://github.com/select2/select2/blob/master/LICENSE.md */
var dalLoadLanguage=function(n){var e;(e=n&&n.fn&&n.fn.select2&&n.fn.select2.amd?n.fn.select2.amd:e).define("select2/i18n/zh-CN",[],function(){return{errorLoading:function(){return"无法载入结果。"},inputTooLong:function(n){return"请删除"+(n.input.length-n.maximum)+"个字符"},inputTooShort:function(n){return"请再输入至少"+(n.minimum-n.input.length)+"个字符"},loadingMore:function(){return"载入更多结果…"},maximumSelected:function(n){return"最多只能选择"+n.maximum+"个项目"},noResults:function(){return"未找到结果"},searching:function(){return"搜索中…"},removeAllItems:function(){return"删除所有项目"}}}),e.define,e.require},event=new CustomEvent("dal-language-loaded",{lang:"zh-CN"});document.dispatchEvent(event);
