/* Agentic AI — shared JS utilities (vanilla, no frameworks) */
'use strict';
function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function fmtTime(iso){return iso?iso.slice(11,19):'--:--:--'}
function fmtBytes(b){if(b<1024)return b+' B';if(b<1048576)return(b/1024).toFixed(1)+' KB';return(b/1048576).toFixed(1)+' MB'}
async function getJSON(url){try{return await(await fetch(url)).json()}catch(e){return null}}
async function postJSON(url,data){try{return await(await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})).json()}catch(e){return null}}
function scrollBottom(el){if(el)el.scrollTop=el.scrollHeight}
