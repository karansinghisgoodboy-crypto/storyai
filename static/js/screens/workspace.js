const Screens=(()=>{
function input(label,name,value,multiline=false){const control=Dom.el(multiline?'textarea':'input',multiline?{name,rows:'4'}:{name,type:'text'});control.value=value||'';return Dom.el('label',{class:'field'},[Dom.el('span',{text:label}),control])}
function formData(form){return Object.fromEntries([...form.elements].filter(control=>control.name).map(control=>[control.name,control.value]))}
const Screens={};
Screens.characters=(box,p)=>CharactersScreen.render(box,p);
Screens.locations=(box,p)=>LocationsScreen.render(box,p);
async function CRUDScreen(box,p,title,type,listFn,createFn,updateFn,deleteFn,lockFn,fields){const render=async()=>{Dom.clear(box);const add=Dom.button('Add '+type,()=>editor(null), 'primary');box.append(Dom.el('div',{class:'page-head'},[Dom.el('div',{},[Dom.el('h2',{class:'section-title',text:title}),Dom.el('p',{class:'muted',text:'Saved in this project. Locked items cannot be changed.'})]),add]));let data;try{data=await listFn(p.id)}catch(e){box.append(Dom.el('p',{class:'message',text:e.message}));return}const items=data[type+'s']||data[title.toLowerCase()]||[];const list=Dom.el('div',{class:'cards'});items.forEach(item=>{const card=Dom.el('article',{class:'card'},[Dom.el('h3',{text:item.name}),Dom.el('p',{class:'muted',text:item.role||item.description||item.mood||''}),Dom.el('p',{class:'small',text:item.locked?'🔒 Locked':'Editable'}),Dom.el('div',{class:'row'},[Dom.button('Edit',()=>editor(item)),Dom.button(item.locked?'Unlock':'Lock',async()=>{try{await lockFn(p.id,item.id,!item.locked,item.updated_at);render()}catch(e){alert(e.message)}}),Dom.button('Delete',async()=>{if(item.locked)return alert('Unlock it first.');if(confirm('Delete '+item.name+'?')){try{await deleteFn(p.id,item.id);render()}catch(e){alert(e.message)}}},'danger')])]);list.append(card)});if(!items.length)list.append(Dom.el('p',{class:'empty',text:'Nothing here yet.'}));box.append(list)};
const editor=async(item)=>{const form=Dom.el('form',{class:'editor'});form.append(Dom.el('h3',{text:item?'Edit '+type:'New '+type}));const limits={name:120,role:120,age:40,build:200,hair:200,face:300,appearance:1000,default_outfit:500,distinguishing_marks:500,personality:1000,backstory:4000,voice:500,abilities:1500,description:3000,mood:500};fields.forEach(k=>form.append(input(k.replaceAll('_',' '),k,item?.[k],['appearance','default_outfit','distinguishing_marks','personality','backstory','abilities','description'].includes(k))));const status=Dom.el('p',{class:'small muted',text:item?'Edit then Save.':'Create to add it.'});form.append(status,Dom.el('div',{class:'row'},[Dom.button(item?'Save':'Create',async()=>{try{const d=item?await updateFn(p.id,item.id,{...formData(form),updated_at:item.updated_at}):await createFn(p.id,formData(form));status.textContent='Saved';render()}catch(e){status.textContent=e.message}},'primary'),Dom.button('Cancel',render)]));box.prepend(form);form.scrollIntoView({behavior:'smooth'})};await render()}
Screens.story=async(box,p)=>{
let story;
try{story=(await Api.getStory(p.id)).story}
catch(error){box.append(Dom.el('p',{class:'message',role:'alert',text:error.message}));return}
const key=`story-${p.id}`;
const form=Dom.el('form',{class:'editor'},[
Dom.el('h2',{class:'section-title',text:'Story'}),
input('Logline','logline',story.logline),
input('Genre','genre',story.genre),
input('Tone','tone',story.tone),
input('Synopsis','synopsis',story.synopsis,true),
input('Story','story_text',story.story_text,true),
]);
const status=Dom.el('p',{class:'small muted','aria-live':'polite',text:'Changes save automatically after a short pause.'});
const save=async()=>{
await AutoSave.settle(key);
try{
story=(await Api.updateStory(p.id,{...formData(form),updated_at:story.updated_at})).story;
status.textContent='Saved';
}catch(error){status.textContent=error.message}
};
for(const field of form.querySelectorAll('input,textarea')){
field.addEventListener('input',()=>AutoSave.schedule(key,async()=>{
story=(await Api.updateStory(p.id,{...formData(form),updated_at:story.updated_at})).story;
},(state,error)=>{
status.textContent=state==='saving'?'Saving…':state==='saved'?'Saved':state==='conflict'?error.message:state==='failed'?'Could not save the story. Check your connection and try again.':'Changes save automatically after a short pause.';
}));
}
form.append(status,Dom.button('Save story',save,'primary'));
box.append(form);
};
Screens.scenes=async(box,p)=>{
let scenes,chars,locs;
try{[scenes,chars,locs]=await Promise.all([Api.listScenes(p.id),Api.listCharacters(p.id),Api.listLocations(p.id)]);scenes=scenes.scenes;chars=chars.characters;locs=locs.locations}
catch(e){box.append(Dom.el('p',{class:'message',role:'alert',text:e.message}));return}
box.append(Dom.el('div',{class:'page-head'},[Dom.el('h2',{class:'section-title',text:'Scenes'}),Dom.button('Add scene',add,'primary')]));
const list=Dom.el('div',{class:'stack'});
if(!scenes.length)list.append(Dom.el('p',{class:'empty',text:'No scenes yet. Add a scene to start your storyboard.'}));
scenes.forEach(scene=>list.append(sceneCard(scene)));
box.append(list);
function sceneCard(scene){
const card=Dom.el('article',{class:'card scene-card','data-scene-id':scene.id});
const form=Dom.el('form');
form.append(input('Title','title',scene.title),input('Summary','summary',scene.summary,true),input('Time of day','time_of_day',scene.time_of_day));
const orderField=input('Scene order','order_no',scene.order_no);
const orderControl=orderField.querySelector('input');
orderControl.type='number';orderControl.min='1';orderControl.step='1';
form.append(orderField);
const locationSelect=Dom.el('select',{name:'location_id','aria-label':'Scene location'});
locationSelect.append(Dom.el('option',{value:'',text:'No location'}));
locs.forEach(place=>locationSelect.append(Dom.el('option',{value:String(place.id),text:place.name})));
locationSelect.value=scene.location_id?String(scene.location_id):'';
form.append(Dom.el('label',{class:'field'},[Dom.el('span',{text:'Location'}),locationSelect]));
const linked=new Map(scene.characters.map(item=>[item.id,item]));
const cast=Dom.el('fieldset',{class:'scene-cast'},[Dom.el('legend',{text:'Characters in this scene'})]);
const selections=[];
for(const character of chars){
const existing=linked.get(character.id);
const checkbox=Dom.el('input',{type:'checkbox','aria-label':`Include ${character.name}`});
checkbox.checked=Boolean(existing);
const outfit=Dom.el('textarea',{rows:'2','aria-label':`${character.name} outfit or state`});
outfit.value=existing?.outfit_state||'';
selections.push({character,checkbox,outfit});
cast.append(Dom.el('div',{class:'scene-character'},[
Dom.el('label',{class:'scene-character-select'},[checkbox,Dom.el('span',{text:character.name})]),
Dom.el('label',{class:'field'},[Dom.el('span',{text:`${character.name} outfit/state (optional)`}),outfit]),
]));
}
if(!chars.length)cast.append(Dom.el('p',{class:'muted',text:'Create a character before linking one to this scene.'}));
form.append(cast);
const status=Dom.el('p',{class:'small muted','aria-live':'polite',text:''});
const characterSummary=Dom.el('p',{class:'small',text:'Characters: '+scene.characters.map(item=>item.name).join(', ')});
const save=async()=>{
try{
const values=formData(form);
const updated=await Api.updateScene(p.id,scene.id,{...values,location_id:locationSelect.value?Number(locationSelect.value):null,status:scene.status,order_no:Number(values.order_no),updated_at:scene.updated_at});
Object.assign(scene,updated.scene);
const characters=selections.filter(entry=>entry.checkbox.checked).map(({character,outfit})=>({character_id:character.id,outfit_state:outfit.value}));
const linkedResponse=await Api.setSceneCharacters(p.id,scene.id,characters,scene.updated_at);
Object.assign(scene,linkedResponse.scene);
characterSummary.textContent='Characters: '+scene.characters.map(item=>item.name).join(', ');
status.textContent='Saved';
}catch(error){status.textContent=error.message}
};
form.append(status,Dom.el('div',{class:'row'},[
Dom.button('Save',save,'primary'),
Dom.button('Storyboard',()=>{location.hash=`#/project/${p.id}/storyboard`}),
Dom.button('Delete',async()=>{if(!window.confirm('Delete scene?'))return;try{await Api.deleteScene(p.id,scene.id);await Screens.scenes(box,p)}catch(error){status.textContent=error.message}},'danger'),
]));
card.append(form,characterSummary);
return card;
}
async function add(){try{const response=await Api.createScene(p.id,{title:'New Scene',summary:'',status:'draft'});Object.assign(response.scene,{characters:[]});scenes.push(response.scene);list.append(sceneCard(response.scene))}catch(error){box.append(Dom.el('p',{class:'message',role:'alert',text:error.message}))}}
};
Screens.storyboard=async(box,p,notice='')=>{
Dom.clear(box);
let scenes;
try{scenes=(await Api.listScenes(p.id)).scenes}
catch(error){box.append(Dom.el('p',{class:'message',role:'alert',text:error.message}));return}
box.append(Dom.el('h2',{class:'section-title',text:'Storyboard'}));
const direction=Dom.el('textarea',{rows:'3','aria-label':'Storyboard direction',placeholder:'Describe the sequence or scene you want StoryAI to storyboard...'});
const generationStatus=Dom.el('p',{class:'small muted','aria-live':'polite',text:notice});
let generating=false;
const generateButton=Dom.button('Generate and save storyboard',async()=>{
if(generating)return;
if(!direction.value.trim()){generationStatus.textContent='Describe what you want storyboarded first.';return}
generating=true;generateButton.disabled=true;generationStatus.textContent='Generating storyboard…';
try{await Api.generateStoryboard(p.id,direction.value.trim());await Screens.storyboard(box,p,'Storyboard generated and saved.')}
catch(error){generationStatus.textContent=error.message}
finally{generating=false;generateButton.disabled=false}
},'primary');
box.append(Dom.el('section',{class:'card storyboard-generator'},[
Dom.el('label',{class:'field'},[Dom.el('span',{text:'Storyboard direction'}),direction]),
generateButton,generationStatus,
]));
if(!scenes.length)box.append(Dom.el('p',{class:'empty',text:'No scenes yet. Generate a storyboard or add a scene first.'}));
for(const scene of scenes){
let shots;
try{shots=(await Api.listShots(p.id,scene.id)).shots}
catch(error){box.append(Dom.el('p',{class:'message',role:'alert',text:error.message}));continue}
const section=Dom.el('section',{class:'storyboard-section'},[Dom.el('h3',{text:`Scene ${scene.order_no}: ${scene.title}`})]);
const grid=Dom.el('div',{class:'shot-grid'});
if(!shots.length)grid.append(Dom.el('p',{class:'empty',text:'No shots yet. Add the first panel for this scene.'}));
shots.forEach(shot=>grid.append(shotCard(scene,shot)));
const status=Dom.el('p',{class:'small muted','aria-live':'polite'});
section.append(grid,Dom.el('div',{class:'row'},[
Dom.button('Add shot',async()=>{try{const result=await Api.createShot(p.id,scene.id,{shot_type:'',camera_angle:'',movement:'',action:'',dialogue:'',lighting:'',notes:''});shots.push(result.shot);grid.replaceChildren(...shots.map(shot=>shotCard(scene,shot)))}catch(error){status.textContent=error.message}},'primary'),
status,
]));
box.append(section);
}
function shotCard(scene,shot){
const form=Dom.el('form',{class:'shot-card','data-shot-id':shot.id},[Dom.el('h4',{text:'Shot '+shot.order_no})]);
const orderField=input('Shot order','order_no',shot.order_no);
const orderControl=orderField.querySelector('input');
orderControl.type='number';orderControl.min='1';orderControl.step='1';
form.append(orderField,input('Shot type','shot_type',shot.shot_type),input('Camera angle','camera_angle',shot.camera_angle),input('Movement','movement',shot.movement),input('Action','action',shot.action,true),input('Dialogue','dialogue',shot.dialogue,true),input('Lighting','lighting',shot.lighting),input('Notes','notes',shot.notes,true));
const status=Dom.el('p',{class:'small muted','aria-live':'polite'});
if(shot.frame?.asset_id)form.append(Dom.el('img',{class:'storyboard-frame',src:`/api/projects/${p.id}/scenes/${scene.id}/shots/${shot.id}/image?updated=${encodeURIComponent(shot.frame.updated_at)}`,alt:`Storyboard frame for shot ${shot.order_no}`}));
const file=Dom.el('input',{type:'file',accept:'.png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp','aria-label':`Choose an image for shot ${shot.order_no}`});
form.append(Dom.el('label',{class:'field'},[Dom.el('span',{text:'Storyboard image (PNG, JPG or WEBP; max 5 MB)'}),file]));
form.append(status,Dom.el('div',{class:'row'},[
Dom.button('Save',async()=>{try{const values=formData(form);const result=await Api.updateShot(p.id,scene.id,shot.id,{...values,order_no:Number(values.order_no),updated_at:shot.updated_at});Object.assign(shot,result.shot);status.textContent='Saved'}catch(error){status.textContent=error.message}},'primary'),
Dom.button('Upload image',async()=>{const selected=file.files[0];if(!selected){status.textContent='Choose an image file first.';return}if(selected.size>5*1024*1024){status.textContent='Image must be 5 MB or smaller.';return}try{const result=await Api.uploadShotImage(p.id,scene.id,shot.id,selected);Object.assign(shot,result.shot);status.textContent='Storyboard image saved.';form.querySelector('.storyboard-frame')?.remove();form.insertBefore(Dom.el('img',{class:'storyboard-frame',src:`/api/projects/${p.id}/scenes/${scene.id}/shots/${shot.id}/image?updated=${encodeURIComponent(shot.frame.updated_at)}`,alt:`Storyboard frame for shot ${shot.order_no}`}),file.parentElement)}catch(error){status.textContent=error.message}},'primary'),
Dom.button('Delete',async()=>{if(!window.confirm('Delete this shot?'))return;try{await Api.deleteShot(p.id,scene.id,shot.id);form.remove()}catch(error){status.textContent=error.message}},'danger'),
]));
return form;
}
};
Screens.continuity=async(box,p)=>{const run=Dom.button('Run continuity check',async()=>{await Api.runContinuity(p.id);location.reload()},'primary');box.append(Dom.el('div',{class:'page-head'},[Dom.el('h2',{class:'section-title',text:'Continuity'},),run]));const d=await Api.continuity(p.id);if(!d.issues.length)box.append(Dom.el('p',{class:'empty',text:'No continuity issues recorded.'}));d.issues.forEach(i=>{const c=Dom.el('article',{class:'card'},[Dom.el('h3',{text:i.severity.toUpperCase()+' · '+i.type}),Dom.el('p',{text:i.description}),Dom.el('p',{class:'muted',text:i.suggested_fix}),Dom.el('div',{class:'row'},[Dom.button('Resolve',async()=>{await Api.issueStatus(p.id,i.id,'resolved');location.reload()}),Dom.button('Dismiss',async()=>{await Api.issueStatus(p.id,i.id,'dismissed');location.reload()})])]);box.append(c)})};
Screens.export=(box,p)=>{box.append(Dom.el('h2',{class:'section-title',text:'Export'}),Dom.el('p',{text:'Download a complete JSON backup or a self-contained printable storyboard HTML.'}),Dom.el('div',{class:'row'},[Dom.el('a',{class:'btn btn-primary',href:`/api/projects/${p.id}/export/json`,text:'Download JSON backup'}),Dom.el('a',{class:'btn btn-primary',href:`/api/projects/${p.id}/export/html`,text:'Download Storyboard HTML'})]));};
Screens.chat=async(box,p)=>{
Dom.clear(box);
box.append(Dom.el('h2',{class:'section-title',text:'AI Chat'}));
const log=Dom.el('div',{class:'chat-log',role:'log','aria-label':'Conversation'});
const mode=Dom.el('select',{id:'search-mode','aria-label':'Search mode'},[
Dom.el('option',{value:'false',text:'Search: Auto'}),
Dom.el('option',{value:'true',text:'Search: On'}),
]);
const message=Dom.el('textarea',{id:'chat-input',rows:'4',placeholder:'Ask StoryAI about your story...','aria-label':'Message'});
const status=Dom.el('p',{class:'small muted','aria-live':'polite'});
let sending=false;
const send=async()=>{
if(sending||!message.value.trim())return;
const text=message.value.trim();
sending=true;status.textContent='Thinking…';
try{
const result=await Api.sendChat(p.id,text,mode.value==='true');
appendMessage(log,'user',text);
appendMessage(log,'assistant',result.reply,result.sources);
message.value='';status.textContent='Saved';
}catch(error){status.textContent=error.message}
finally{sending=false}
};
const suggest=async()=>{
if(!message.value.trim()){status.textContent='Enter a message before asking for suggestions.';return}
status.textContent='Creating suggestions…';
try{
const result=await Api.suggest(p.id,message.value.trim());
status.textContent=`${result.proposals.length} suggestion(s) created. Review them before applying.`;
}catch(error){status.textContent=error.message}
};
box.append(log,Dom.el('div',{class:'composer'},[
Dom.el('label',{for:'search-mode',text:'Search mode'}),mode,
message,
Dom.el('div',{class:'row'},[
Dom.button('Send',send,'primary'),
Dom.button('Suggest updates',suggest),
Dom.button('Review suggestions',()=>Screens.proposals(box,p)),
Dom.button('Structured memory',()=>Screens.memory(box,p)),
]),
status,
]));
try{
const history=(await Api.history(p.id)).messages;
history.forEach(item=>appendMessage(log,item.role,item.content,item.sources));
}catch(error){status.textContent=error.message}
};
function appendMessage(log,role,content,sources=[]){
log.append(Dom.el('div',{class:`chat ${role}`},[
Dom.el('b',{text:role==='user'?'You':'StoryAI'}),
Dom.el('p',{text:content}),
]));
if(sources.length)log.append(Dom.el('p',{class:'small muted',text:'Sources: '+sources.map(source=>source.title||source.url).join(' · ')}));
}
Screens.memory=async(box,p)=>{
Dom.clear(box);
const status=Dom.el('p',{class:'small muted','aria-live':'polite'});
box.append(Dom.el('div',{class:'page-head'},[
Dom.el('div',{},[Dom.el('h2',{class:'section-title',text:'Structured memory'}),Dom.el('p',{class:'muted',text:'Project facts and rules stay under your control.'})]),
Dom.el('div',{class:'row'},[Dom.button('Back to chat',()=>Screens.chat(box,p)),Dom.button('Add memory',async()=>{try{await Api.createMemory(p.id,{kind:'note',content:'New memory'});await Screens.memory(box,p)}catch(error){status.textContent=error.message}},'primary')]),
]));
box.append(status);
try{
const result=await Api.listMemory(p.id);
if(!result.memory.length)box.append(Dom.el('p',{class:'empty',text:'No saved memory yet.'}));
for(const item of result.memory){
const kind=Dom.el('select',{name:'kind','aria-label':'Memory type'},['fact','rule','theme','note'].map(value=>Dom.el('option',{value,text:value[0].toUpperCase()+value.slice(1)})));
kind.value=item.kind;
const content=Dom.el('textarea',{name:'content',rows:'3','aria-label':'Memory content'});
content.value=item.content;
kind.disabled=content.disabled=item.locked;
const cardStatus=Dom.el('p',{class:'small muted','aria-live':'polite',text:item.locked?'Locked':'Editable'});
const card=Dom.el('article',{class:'card memory-card'},[
Dom.el('label',{class:'field'},[Dom.el('span',{text:'Type'}),kind]),
Dom.el('label',{class:'field'},[Dom.el('span',{text:'Fact or rule'}),content]),
cardStatus,
Dom.el('div',{class:'row'},[
item.locked?Dom.disabledButton("Save","Unlock this memory item before editing."):Dom.button('Save',async()=>{try{const updated=await Api.updateMemory(p.id,item.id,{kind:kind.value,content:content.value,updated_at:item.updated_at});item.updated_at=updated.item.updated_at;cardStatus.textContent='Saved'}catch(error){cardStatus.textContent=error.message}},'primary'),
Dom.button(item.locked?'Unlock':'Lock',async()=>{try{await Api.lockMemory(p.id,item.id,!item.locked,item.updated_at);await Screens.memory(box,p)}catch(error){cardStatus.textContent=error.message}}),
item.locked?Dom.disabledButton("Delete","Unlock this memory item before deleting it.","danger"):Dom.button('Delete',async()=>{if(!window.confirm('Delete this memory item?'))return;try{await Api.deleteMemory(p.id,item.id);await Screens.memory(box,p)}catch(error){cardStatus.textContent=error.message}},'danger'),
]),
]);
box.append(card);
}
}catch(error){status.textContent=error.message}
};
Screens.proposals=async(box,p)=>{
Dom.clear(box);
const status=Dom.el('p',{class:'small muted','aria-live':'polite'});
box.append(Dom.el('div',{class:'page-head'},[
Dom.el('div',{},[Dom.el('h2',{class:'section-title',text:'Suggestions'}),Dom.el('p',{class:'muted',text:'Review every proposed canon change before accepting it.'})]),
Dom.button('Back to chat',()=>Screens.chat(box,p)),
]));
box.append(status);
try{
const result=await Api.proposals(p.id);
if(!result.proposals.length)box.append(Dom.el('p',{class:'empty',text:'No pending suggestions.'}));
for(const item of result.proposals){
let payload=item.payload;
try{payload=JSON.stringify(JSON.parse(item.payload),null,2)}catch{}
const card=Dom.el('article',{class:'card proposal-card'},[
Dom.el('h3',{text:`${item.type} · ${item.action}`}),
Dom.el('p',{text:item.reason}),
Dom.el('pre',{text:payload}),
Dom.el('div',{class:'row'},[
Dom.button('Accept',async()=>{try{await Api.resolveProposal(p.id,item.id,true);await Screens.proposals(box,p)}catch(error){status.textContent=error.message}},'primary'),
Dom.button('Reject',async()=>{try{await Api.resolveProposal(p.id,item.id,false);await Screens.proposals(box,p)}catch(error){status.textContent=error.message}},'danger'),
]),
]);
box.append(card);
}
}catch(error){status.textContent=error.message}
};
return Screens;
})();

const SECTIONS=[
  {key: "chat", label: "Chat",icon:'✦',render:Screens.chat},
  {key: "characters", label: "Characters",icon:'♟',render:Screens.characters},
  {key: "locations", label: "Locations",icon:'⌖',render:Screens.locations},
  {key: "story", label: "Story",icon:'▤',render:Screens.story},
  {key: "scenes", label: "Scenes",icon:'▦',render:Screens.scenes},
  {key: "storyboard", label: "Storyboard",icon:'▧',render:Screens.storyboard},
  {key: "continuity", label: "Continuity",icon:'✓',render:Screens.continuity},
  {key: "export", label: "Export",icon:'⇩',render:Screens.export}
];

const WorkspaceScreen={
  mountedProjectId:null,
  async show(pid,section){
    if(this.mountedProjectId===pid&&State.currentProject){this.showSection(section);return}
    const root=document.getElementById('app'); Dom.clear(root);
    root.append(Dom.el('p',{class:'muted',text:'Opening project…'}));
    try{const d=await Api.getProject(pid);State.currentProject=d.project;this.mountedProjectId=pid;this.build(root,d.project);this.showSection(section||'chat')}
    catch(e){Dom.clear(root);root.append(Dom.el('div',{class:'message',text:e.message}))}
  },
  build(root,p){
    const links=SECTIONS.map(s=>Dom.el('a',{href:`#/project/${p.id}/${s.key}`, 'data-section':s.key,'aria-label':s.label},[Dom.el('span',{class:'nav-icon',text:s.icon}),Dom.el('span',{text:s.label})]));
    Dom.clear(root);
    const back=Dom.el('a',{href:'#/',class:'back',text:'← All projects'});
    const head=Dom.el('header',{class:'workspace-head'},[back,Dom.el('p',{class:'eyebrow',text:'Story workspace'}),Dom.el('h1',{text:p.title}),p.logline?Dom.el('p',{class:'logline',text:p.logline}):Dom.el('p',{class:'logline',text:'Build your story, one decision at a time.'})]);
    const nav=Dom.el('nav',{class:'side-nav','aria-label':'Project sections'},links);
    const content=Dom.el('section',{id:'section-content',class:'section-content'});
    root.append(head,Dom.el('div',{id:'workspace-shell',class:'workspace'},[nav,content]));
  },
  showSection(key){
    const p=State.currentProject,s=SECTIONS.find(x=>x.key===(key||'chat')),box=document.getElementById('section-content');
    if(!box)return;
    document.querySelectorAll('.side-nav a').forEach(a=>a.toggleAttribute('aria-current',a.dataset.section===s?.key));
    Dom.clear(box);
    if(!s){box.append(Dom.el('div',{class:'content-panel'},[Dom.el('h2',{text:'Page not found'})]));return}
    const panel=Dom.el('div',{class:'content-panel'});box.append(panel);
    try{const result=s.render(panel,p);if(result?.catch)result.catch(e=>{Dom.clear(panel);panel.append(Dom.el('div',{class:'message',text:e.message}))})}
    catch(e){panel.append(Dom.el('div',{class:'message',text:e.message}))}
  }
};
