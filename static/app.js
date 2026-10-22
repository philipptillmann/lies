'use strict';
const $ = id => document.getElementById(id);
const state = {config:null, feeds:[], vocabulary:[], selected:null, articles:[], load:0, lookup:0};
function el(tag, text, className) { const node=document.createElement(tag); if(text!==undefined)node.textContent=text; if(className)node.className=className; return node; }
function button(text, action, className) { const node=el('button',text,className);node.onclick=action;return node; }
function status(text='', error=false) { $('status').textContent=text;$('status').className=error?'error':''; }
async function api(path, data) {
 const response=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 const body=await response.json();if(!response.ok)throw new Error(body.error||'Anfrage fehlgeschlagen.');return body;
}
function languageOptions(select, value) { for(const [code,name] of Object.entries(state.config.languages)){const o=el('option',name);o.value=code;select.append(o);}select.value=value; }
function empty(target,title,text) { const box=el('div',undefined,'empty');box.append(el('strong',title),el('p',text));target.append(box); }
function showTab(vocab) {$('reading').hidden=vocab;$('vocabulary').hidden=!vocab;$('read-tab').classList.toggle('active',!vocab);$('vocab-tab').classList.toggle('active',vocab);}
async function refresh() { [state.feeds,state.vocabulary]=await Promise.all([api('/api/feeds'),api('/api/vocabulary')]);renderFeeds();renderVocabulary(); }
function renderFeeds() {
 const holder=$('feeds');holder.replaceChildren();
 const feeds=state.feeds.filter(f=>f.language===$('learning').value);
 for(const feed of feeds){const row=el('div',undefined,'feed-row');const open=button(feed.name,()=>loadFeed(feed),'feed-button'+(state.selected?.id===feed.id?' active':''));const remove=button('×',async()=>{try{await api('/api/feeds/delete',{id:feed.id});if(state.selected?.id===feed.id){state.load++;state.selected=null;resetReader();}await refresh();status('Abo entfernt.');}catch(e){status(e.message,true);}},'remove');remove.setAttribute('aria-label',feed.name+' entfernen');row.append(open,remove);holder.append(row);}
 if(!feeds.length)holder.append(el('p','Noch keine Quellen in dieser Sprache.','aside-note'));
 renderCatalog();
}
function renderCatalog(){
 const holder=$('catalog');holder.replaceChildren();
 for(const feed of state.config.catalog.filter(f=>f.language===$('learning').value)){const row=el('div',undefined,'catalog-item');row.append(el('span',feed.name));const subscribed=state.feeds.some(f=>f.url===feed.url);const add=button(subscribed?'✓':'＋',()=>subscribe(feed,add));add.disabled=subscribed;add.setAttribute('aria-label',feed.name+' abonnieren');row.append(add);holder.append(row);}
 if(!holder.children.length)holder.append(el('p','Füge unten einen öffentlichen RSS-Feed für diese Sprache hinzu.'));
}
async function subscribe(feed, control){control.disabled=true;status('Feed wird geprüft …');try{await api('/api/feeds',feed);await refresh();status('Quelle abonniert. Viel Spaß beim Lesen!');const added=state.feeds.find(f=>f.url===feed.url);if(added?.language===$('learning').value)await loadFeed(added);}catch(e){status(e.message,true);}finally{control.disabled=false;}}
function resetReader(){$('reader').hidden=true;$('articles').hidden=false;$('articles').replaceChildren();$('feed-title').textContent='Dein Lesestoff';empty($('articles'),'Eine Welt voller Geschichten.','Wähle eine Quelle oder abonniere deinen ersten Feed über „＋ Abo“.');}
async function loadFeed(feed){
 const ticket=++state.load;state.selected=feed;renderFeeds();$('feed-title').textContent=feed.name;$('reader').hidden=true;$('articles').hidden=false;$('articles').replaceChildren();status('Nachrichten werden geladen …');
 try{const articles=await api('/api/articles/'+feed.id);if(ticket!==state.load)return;state.articles=articles;renderArticles();status();}catch(e){if(ticket!==state.load)return;status(e.message,true);empty($('articles'),'Gerade keine Verbindung.','Versuche es später erneut oder wähle eine andere Quelle.');}
}
function renderArticles(){
 const holder=$('articles');holder.replaceChildren();$('reader').hidden=true;holder.hidden=false;
 for(const article of state.articles){const card=el('div',undefined,'card');card.append(el('span',state.selected.name,'meta'),el('h3',article.title),el('p',article.text.slice(0,190)+(article.text.length>190?'…':'')),button('Lesen & entdecken ↗',()=>readArticle(article)));holder.append(card);}
}
function sentences(text, language){if(Intl.Segmenter)return [...new Intl.Segmenter(language,{granularity:'sentence'}).segment(text)].map(s=>s.segment);return text.match(/[^.!?]+[.!?]*/gu)||[text];}
function tokenized(text, article, language){
 const fragment=document.createDocumentFragment();
 for(const sentence of sentences(text,language)){
 const segments=Intl.Segmenter?[...new Intl.Segmenter(language,{granularity:'word'}).segment(sentence)].map(s=>({text:s.segment,word:s.isWordLike})):sentence.split(/([\p{L}\p{M}]+(?:['’\-][\p{L}\p{M}]+)*)/gu).map(t=>({text:t,word:/^[\p{L}\p{M}]/u.test(t)}));
 for(const token of segments){if(token.word&&/[\p{L}]/u.test(token.text)){const b=button(token.text,()=>lookup(token.text,sentence,article,language),'word');b.setAttribute('aria-label',token.text+' übersetzen');fragment.append(b);}else fragment.append(document.createTextNode(token.text));}}
 return fragment;
}
function readArticle(article){
 const language=state.selected.language,reader=$('reader');reader.replaceChildren();$('articles').hidden=true;reader.hidden=false;
 reader.append(button('← Alle Beiträge',renderArticles),el('p',state.selected.name,'meta'));
 const title=el('h2');title.append(tokenized(article.title,article,language));reader.append(title);
 const body=el('div',undefined,'body');body.append(tokenized(article.text||'Dieser Feed enthält nur die Überschrift.',article,language));reader.append(body);
 reader.append(el('small','Du liest den vom RSS-Feed bereitgestellten Text. Tippe ein Wort an, um es zu übersetzen und mit diesem Satz zu speichern.'));
 if(article.url){const p=el('p');const a=el('a','Vollständigen Originalartikel öffnen ↗');a.href=article.url;a.target='_blank';a.rel='noopener noreferrer';p.append(a);reader.append(p);}
}
async function lookup(word,sentence,article,source){
 const ticket=++state.lookup, target=$('native').value;const dialog=$('translation');$('lookup-word').textContent=word;$('lookup-result').textContent='Übersetzung wird geladen …';$('wiktionary').href='https://'+source+'.wiktionary.org/wiki/'+encodeURIComponent(word.toLowerCase());if(!dialog.open)dialog.showModal();
 try{const result=await api('/api/lookup',{word,sentence,source,target,article_title:article.title,article_url:article.url});if(ticket===state.lookup)$('lookup-result').textContent=result.translation+' · ✓ gespeichert';state.vocabulary=await api('/api/vocabulary');renderVocabulary();}
 catch(e){if(ticket===state.lookup)$('lookup-result').textContent=e.message;}
}
function renderVocabulary(){
 $('count').textContent=state.vocabulary.length;const holder=$('vocab-list');holder.replaceChildren();$('export').disabled=!state.vocabulary.length;
 if(!state.vocabulary.length)empty(holder,'Deine Wörter warten auf dich.','Tippe beim Lesen ein unbekanntes Wort an. Nach der Übersetzung landet es hier – zusammen mit seinem Satz.');
 for(const v of state.vocabulary){const card=el('div',undefined,'vocab-card');const word=el('div');word.append(el('h3',v.word),el('p',v.translation),el('small',state.config.languages[v.source_language]+' → '+state.config.languages[v.target_language]));const context=el('div');context.append(el('blockquote',v.sentence));if(v.article_url){const a=el('a',v.article_title||'Quelle öffnen');a.href=v.article_url;a.target='_blank';a.rel='noopener noreferrer';context.append(a);}else context.append(el('small',v.article_title));card.append(word,context,button('Entfernen',async()=>{try{await api('/api/vocabulary/delete',{id:v.id});state.vocabulary=await api('/api/vocabulary');renderVocabulary();}catch(e){status(e.message,true);}}));holder.append(card);}
}
$('read-tab').onclick=()=>showTab(false);$('vocab-tab').onclick=()=>showTab(true);
$('add-toggle').onclick=()=>{$('add-panel').hidden=!$('add-panel').hidden;$('add-toggle').setAttribute('aria-expanded',String(!$('add-panel').hidden));};
$('close-dialog').onclick=()=>{$('translation').close();state.lookup++;};
$('learning').onchange=()=>{localStorage.setItem('lies-learning',$('learning').value);state.load++;state.selected=null;resetReader();renderFeeds();status();};
$('native').onchange=()=>localStorage.setItem('lies-native',$('native').value);
$('feed-form').onsubmit=async event=>{event.preventDefault();const form=event.target, data=new FormData(form);await subscribe({name:data.get('name'),url:data.get('url'),language:$('learning').value},form.querySelector('button'));};
$('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(state.vocabulary,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download='lies-vokabeln.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
(async()=>{try{state.config=await api('/api/config');let learning='en',native='de';try{learning=localStorage.getItem('lies-learning')||learning;native=localStorage.getItem('lies-native')||native;}catch{}languageOptions($('learning'),state.config.languages[learning]?learning:'en');languageOptions($('native'),state.config.languages[native]?native:'de');await refresh();resetReader();if(!state.feeds.length){$('add-panel').hidden=false;$('add-toggle').setAttribute('aria-expanded','true');}}catch(e){status('Start fehlgeschlagen: '+e.message,true);}})();
