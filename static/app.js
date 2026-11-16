'use strict';
const $ = id => document.getElementById(id);
const state = {config:null, feeds:[], vocabulary:[], selected:null, articles:[], load:0, lookup:0, readerTicket:0};
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
function resetReader(){state.readerTicket++;$('reader').hidden=true;$('articles').hidden=false;$('articles').replaceChildren();$('feed-title').textContent='Dein Lesestoff';empty($('articles'),'Eine Welt voller Geschichten.','Wähle eine Quelle oder abonniere deinen ersten Feed über „＋ Abo“.');}
async function loadFeed(feed){
 const ticket=++state.load;state.selected=feed;renderFeeds();$('feed-title').textContent=feed.name;$('reader').hidden=true;$('articles').hidden=false;$('articles').replaceChildren();status('Nachrichten werden geladen …');
 try{const articles=await api('/api/articles/'+feed.id);if(ticket!==state.load)return;state.articles=articles;renderArticles();status();}catch(e){if(ticket!==state.load)return;status(e.message,true);empty($('articles'),'Gerade keine Verbindung.','Versuche es später erneut oder wähle eine andere Quelle.');}
}
function renderArticles(){
 state.readerTicket++;
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
 const language=state.selected.language, feedId=state.selected.id, ticket=++state.readerTicket,reader=$('reader');reader.replaceChildren();$('articles').hidden=true;reader.hidden=false;
 reader.append(button('← Alle Beiträge',renderArticles),el('p',state.selected.name,'meta'));
 const title=el('h2');title.append(tokenized(article.title,article,language));reader.append(title);
 const note=el('p',article.fullText?'Artikeltext aus dem Original · automatisch extrahiert':'RSS-Auszug · Viele Quellen liefern nur eine Zusammenfassung.','reader-note');reader.append(note);
 const body=el('div',undefined,'body');
 if(article.fullText||article.text)body.append(tokenized(article.fullText||article.text,article,language));
 else body.append(el('p','Dieser Feed enthält nur die Überschrift.'));
 reader.append(body);
 if(article.url){
   if(!article.fullText){const load=button('Artikeltext hier laden',async()=>{
     load.disabled=true;note.textContent='Artikeltext wird vom Original geladen …';
     try{const result=await api('/api/article',{feed_id:feedId,url:article.url});article.fullText=result.text;if(ticket!==state.readerTicket)return;readArticle(article);}
     catch(e){if(ticket!==state.readerTicket)return;note.textContent=e.message+' Der RSS-Auszug bleibt lesbar.';load.disabled=false;}
   },'primary');reader.append(load);}
   else reader.append(button('RSS-Auszug anzeigen',()=>{delete article.fullText;readArticle(article);}));
 }
 reader.append(el('p','Tippe ein Wort an, um Übersetzungen zu sehen und es mit seinem Satz zu speichern.','reader-note'));
 if(article.url){const p=el('p');const a=el('a','Vollständigen Originalartikel öffnen ↗');a.href=article.url;a.target='_blank';a.rel='noopener noreferrer';p.append(a);reader.append(p);}
}
function translationsOf(item){return item.translations?.length?item.translations:[{text:item.translation,sense:'',provider:'Gespeichert'}];}
function translationList(items){const list=el('ul',undefined,'translations');for(const item of items){const li=el('li');li.append(el('strong',item.text));if(item.sense)li.append(el('span',item.sense,'sense'));if(item.source_url){const credit=el('a',item.provider);credit.href=item.source_url;credit.target='_blank';credit.rel='noopener noreferrer';const small=el('small');small.append(credit);li.append(small);}else li.append(el('small',item.provider));list.append(li);}return list;}

async function lookup(word,sentence,article,source){
 const ticket=++state.lookup, target=$('native').value;const dialog=$('translation');$('lookup-word').textContent=word;$('lookup-result').textContent='Übersetzung wird geladen …';$('wiktionary').href='https://'+source+'.wiktionary.org/wiki/'+encodeURIComponent(word.toLowerCase());if(!dialog.open)dialog.showModal();
 try{const result=await api('/api/lookup',{word,sentence,source,target,article_title:article.title,article_url:article.url});if(ticket===state.lookup)$('lookup-result').replaceChildren(translationList(translationsOf(result)),el('small','✓ Alle angezeigten Übersetzungen mit Satz gespeichert.'));state.vocabulary=await api('/api/vocabulary');renderVocabulary();}
 catch(e){if(ticket===state.lookup)$('lookup-result').textContent=e.message;}
}
function selectedVocabulary(){return state.vocabulary.filter(v=>v.source_language===$('vocab-language').value);}
function renderVocabulary(){
 const vocabulary=selectedVocabulary();
 for(const option of $('vocab-language').options){const count=state.vocabulary.filter(v=>v.source_language===option.value).length;option.textContent=state.config.languages[option.value]+' ('+count+')';}
 $('vocab-summary').textContent=state.config.languages[$('vocab-language').value]+' · '+vocabulary.length+' Wörter';
 $('count').textContent=vocabulary.length;const holder=$('vocab-list');holder.replaceChildren();$('export').disabled=!vocabulary.length;
 if(!vocabulary.length)empty(holder,'Deine Wörter warten auf dich.','Tippe beim Lesen ein unbekanntes Wort an. Nach der Übersetzung landet es hier – zusammen mit seinem Satz.');
 for(const v of vocabulary){const card=el('div',undefined,'vocab-card');const word=el('div');word.append(el('h3',v.word),translationList(translationsOf(v)),el('small',state.config.languages[v.source_language]+' → '+state.config.languages[v.target_language]));const context=el('div');context.append(el('blockquote',v.sentence));if(v.article_url){const a=el('a',v.article_title||'Quelle öffnen');a.href=v.article_url;a.target='_blank';a.rel='noopener noreferrer';context.append(a);}else context.append(el('small',v.article_title));card.append(word,context,button('Entfernen',async()=>{try{await api('/api/vocabulary/delete',{id:v.id});state.vocabulary=await api('/api/vocabulary');renderVocabulary();}catch(e){status(e.message,true);}}));holder.append(card);}
}
$('read-tab').onclick=()=>showTab(false);$('vocab-tab').onclick=()=>showTab(true);
$('add-toggle').onclick=()=>{$('add-panel').hidden=!$('add-panel').hidden;$('add-toggle').setAttribute('aria-expanded',String(!$('add-panel').hidden));};
$('close-dialog').onclick=()=>{$('translation').close();state.lookup++;};
$('learning').onchange=()=>{localStorage.setItem('lies-learning',$('learning').value);state.load++;state.selected=null;resetReader();renderFeeds();$('vocab-language').value=$('learning').value;renderVocabulary();status();};
$('vocab-language').onchange=renderVocabulary;
$('native').onchange=()=>localStorage.setItem('lies-native',$('native').value);
$('feed-form').onsubmit=async event=>{event.preventDefault();const form=event.target, data=new FormData(form);await subscribe({name:data.get('name'),url:data.get('url'),language:$('learning').value},form.querySelector('button'));};
$('export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(selectedVocabulary(),null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download='lies-vokabeln-'+$('vocab-language').value+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
(async()=>{try{state.config=await api('/api/config');let learning='en',native='de';try{learning=localStorage.getItem('lies-learning')||learning;native=localStorage.getItem('lies-native')||native;}catch{}languageOptions($('learning'),state.config.languages[learning]?learning:'en');languageOptions($('native'),state.config.languages[native]?native:'de');languageOptions($('vocab-language'),$('learning').value);await refresh();resetReader();if(!state.feeds.length){$('add-panel').hidden=false;$('add-toggle').setAttribute('aria-expanded','true');}}catch(e){status('Start fehlgeschlagen: '+e.message,true);}})();

