const CHARACTER_FIELDS = [
  ["name","Name","text",true],["role","Role","text"],["age","Age","text"],["build","Build","text"],
  ["hair","Hair","text"],["face","Face","text"],["appearance","Appearance","textarea"],["default_outfit","Default outfit","textarea"],
  ["distinguishing_marks","Distinguishing marks","textarea"],["personality","Personality","textarea"],["backstory","Backstory","textarea"],
  ["voice","Voice","textarea"],["abilities","Abilities","textarea"]
];
const CharactersScreen = {
  render(box, project) {
    this.project = project; this.box = box; this.selected = null;
    this.draw();
  },
  async draw() {
    const box=this.box; Dom.clear(box);
    const header=Dom.el("div",{class:"page-head"},[Dom.el("div",{},[Dom.el("h2",{class:"section-title",text:"Characters"}),Dom.el("p",{class:"muted",text:"Create and maintain fixed character sheets for story consistency."})]),Dom.button("Add character",()=>this.add(),"primary")]);
    box.append(header);
    try { const d=await Api.listCharacters(this.project.id); if(!this.box)return; this.characters=d.characters; this.drawList(); }
    catch(e){box.append(Dom.el("p",{class:"message",text:e.message}));}
  },
  drawList(){
    const list=Dom.el("div",{class:"character-list"});
    if(!this.characters.length) list.append(Dom.el("p",{class:"empty",text:"No characters yet. Add the first character to begin your cast."}));
    for(const c of this.characters){
      const card=Dom.el("article",{class:"character-card"});
      const img=c.image_id?Dom.el("img",{class:"character-thumb",src:"/api/projects/"+this.project.id+"/characters/"+c.id+"/image",alt:"Reference image for "+c.name}):Dom.el("div",{class:"character-thumb placeholder",text:"No image"});
      const info=Dom.el("div",{class:"character-info"},[Dom.el("h3",{text:c.name}),c.role?Dom.el("p",{class:"muted",text:c.role}):null,Dom.el("p",{class:"small",text:c.locked?"Locked":"Editable"})]);
      card.append(img,info,Dom.el("div",{class:"row"},[c.locked?Dom.disabledButton("Edit","Unlock this character before editing."):Dom.button("Edit",()=>this.edit(c)),Dom.button(c.locked?"Unlock":"Lock",()=>this.toggleLock(c)),Dom.button("Delete",()=>this.remove(c),"danger")])); list.append(card);
    }
    this.box.append(list);
  },
  async add(){ const c={id:null,project_id:this.project.id,locked:false,updated_at:null}; this.openForm(c,true); },
  edit(c){if(c.locked)return;this.openForm({...c},false);},
  openForm(c,isNew){
    const old=this.box.querySelector(".character-editor"); old?.remove();
    const form=Dom.el("form",{class:"character-editor"});
    form.append(Dom.el("div",{class:"page-head"},[Dom.el("h3",{text:isNew?"New character":"Edit character"}),Dom.button("Close",()=>form.remove())]));
    for(const [key,label,type,required] of CHARACTER_FIELDS){ const wrap=Dom.el("div"); wrap.append(Dom.el("label",{for:"char-"+key,text:label+(required?" *":"")})); const input=type==="textarea"?Dom.el("textarea",{id:"char-"+key,rows:key==="backstory"?5:3}):Dom.el("input",{id:"char-"+key,type:"text"}); input.value=c[key]||""; if(required)input.required=true; wrap.append(input); form.append(wrap); }
    if(c.image_id)form.append(Dom.el("img",{class:"character-thumb",src:"/api/projects/"+this.project.id+"/characters/"+c.id+"/image",alt:"Reference image for "+c.name}));
    const status=Dom.el("p",{class:"small muted",text:isNew?"Fill the sheet, then Create.":"Changes save automatically after a short pause."});
    if (!isNew) {
      for (const [key] of CHARACTER_FIELDS) {
        const input=form.querySelector("#char-"+key);
        input.addEventListener("input", () => AutoSave.schedule("character-"+c.id, async () => {
          const data={updated_at:c.updated_at}; for(const [f] of CHARACTER_FIELDS)data[f]=form.querySelector("#char-"+f).value;
          const d=await Api.updateCharacter(this.project.id,c.id,data); Object.assign(c,d.character); status.textContent="Saved";
        }, (state,err) => { status.textContent=state==="conflict"?err.message:state==="failed"?"Couldn’t save changes. Please try again.":state==="saving"?"Saving…":"Saved"; }));
      }
    }
    const saveButton=Dom.button(isNew?"Create":"Save",async()=>{await this.saveForm(form,c,isNew,status,saveButton)},"primary"); const buttons=Dom.el("div",{class:"row"},[saveButton]); form.append(status,buttons);
    const file=Dom.el("input",{type:"file",accept:"image/png,image/jpeg,image/webp"}); const upload=async()=>{if(!c.id){status.textContent="Save the character before uploading an image.";return;} if(file.files[0]?.size>5*1024*1024){status.textContent="Image must be 5 MB or smaller.";return;} try{const d=await Api.uploadCharacterImage(this.project.id,c.id,file.files[0]); Object.assign(c,d.character);status.textContent="Reference image saved.";this.draw();}catch(e){status.textContent=e.message;}}; const uploadBtn=c.locked?Dom.disabledButton("Upload reference","Unlock this character before changing its image."):Dom.button("Upload reference",upload); form.append(Dom.el("label",{text:"Reference image (PNG, JPG, WEBP; max 5 MB)"}),file,Dom.el("div",{class:"row"},[uploadBtn]));
    this.box.append(form); form.scrollIntoView({behavior:"smooth",block:"start"});
  },
  async saveForm(form,c,isNew,status,saveButton){
    const controls=[...form.querySelectorAll("input,textarea")];
    controls.forEach(control=>control.disabled=true); saveButton.disabled=true;
    try{if(!isNew)await AutoSave.settle("character-"+c.id);const data={updated_at:c.updated_at}; for(const [key] of CHARACTER_FIELDS)data[key]=form.querySelector("#char-"+key).value;let d;if(isNew)d=await Api.createCharacter(this.project.id,data);else{d=await Api.updateCharacter(this.project.id,c.id,data);Object.assign(c,d.character);}status.textContent="Saved";this.draw();}catch(e){controls.forEach(control=>control.disabled=false);saveButton.disabled=false;status.textContent=e.message;}
  },
  async toggleLock(c){try{const d=await Api.lockCharacter(this.project.id,c.id,!c.locked,c.updated_at);this.draw();}catch(e){alert(e.message);}},
  async remove(c){if(c.locked){alert("Unlock this character before deleting it.");return;}if(!window.confirm(`Delete character "${c.name}"? This cannot be undone.`))return;try{await Api.deleteCharacter(this.project.id,c.id);this.draw();}catch(e){alert(e.message);}}
};
