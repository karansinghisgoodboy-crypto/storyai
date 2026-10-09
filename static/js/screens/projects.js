const ProjectsScreen = {
  async show() {
    const navId = State.navId;
    State.currentProject = null;
    document.title = "StoryAI — Projects";
    const root = document.getElementById("app"); Dom.clear(root);

    const message = Dom.el("div", { class: "message", role: "alert" }); message.hidden = true;
    const list = Dom.el("div", { class: "frames" });
    const titleInput = Dom.el("input", {type:"text", id:"new-title", maxlength:"120", autocomplete:"off", placeholder:"e.g. The Last Signal"});
    const ideaInput = Dom.el("input", {type:"text", id:"new-idea", maxlength:"500", autocomplete:"off", placeholder:"A short idea or premise (optional)"});
    const createPanel = Dom.el("div", {class:"create-panel"}, [
      Dom.el("p",{class:"eyebrow",text:"New workspace"}), Dom.el("h2",{text:"Start a new story"}),
      Dom.el("p",{class:"page-subtitle",text:"Give your project a name. You can shape the story later."}),
      Dom.el("label",{for:"new-title",text:"Project title"}),titleInput,
      Dom.el("label",{for:"new-idea",text:"One-line idea"}),ideaInput,
      Dom.el("div",{class:"row"},[Dom.button("Create project",createProject,"primary"),Dom.button("Cancel",()=>{createPanel.hidden=true})])
    ]); createPanel.hidden=true;
    titleInput.addEventListener("keydown",e=>{if(e.key==="Enter")createProject()});
    root.append(
      Dom.el("div",{class:"page-head"},[Dom.el("div",{},[Dom.el("p",{class:"eyebrow",text:"Workspace"}),Dom.el("h1",{text:"Your projects"}),Dom.el("p",{class:"page-subtitle",text:"Create, organize and develop every story from one place."})]),Dom.button("＋ New Project",openCreatePanel,"primary")]),
      message,createPanel,list
    );
    await loadList();
    function showMessage(text,retryLabel){Dom.clear(message);message.append(Dom.el("span",{text}));if(retryLabel)message.append(Dom.button(retryLabel,loadList));message.hidden=false}
    function openCreatePanel(){createPanel.hidden=false;titleInput.focus()}
    async function loadList(){message.hidden=true;try{const data=await Api.listProjects();if(navId!==State.navId)return;renderList(data.projects)}catch(error){if(navId===State.navId)showMessage(error.message,"Try again")}}
    function renderList(projects){Dom.clear(list);if(!projects.length){list.append(Dom.el("div",{class:"empty"},[Dom.el("p",{class:"eyebrow",text:"First project"}),Dom.el("h2",{text:"Your story starts here"}),Dom.el("p",{class:"muted",text:"Create a project to open the StoryAI workspace."}),Dom.button("Create your first project",openCreatePanel,"primary")]));openCreatePanel();return}projects.forEach(project=>list.append(buildCard(project)))}
    async function createProject(){message.hidden=true;try{const data=await Api.createProject(titleInput.value,ideaInput.value);window.location.hash="#/project/"+data.project.id}catch(error){showMessage(error.message)}}
    function buildCard(project){
      const card=Dom.el("article",{class:"frame"}); const note=Dom.el("p",{class:"message",role:"alert"});note.hidden=true;
      function showNote(error){Dom.clear(note);note.append(Dom.el("span",{text:error.message}));if(error.status===404||error.status===409)note.append(Dom.button("Reload latest",loadList));note.hidden=false}
      function draw(mode){Dom.clear(card);card.append(Dom.el("div",{class:"frame-screen"},[Dom.el("div",{},[Dom.el("p",{class:"eyebrow",text:"Story project"}),Dom.el("h2",{class:"frame-title",text:project.title})]) ]));const caption=Dom.el("div",{class:"frame-caption"});card.append(caption);if(mode==="rename")drawRename(caption);else if(mode==="delete")drawDelete(caption);else drawView(caption)}
      function drawView(caption){caption.append(Dom.el("p",{class:"logline",text:project.logline||"No premise added yet."}),Dom.el("p",{class:"small muted",text:"Updated "+Dom.formatDate(project.updated_at)}),Dom.el("div",{class:"row"},[Dom.button("Open workspace",()=>{window.location.hash="#/project/"+project.id},"primary"),Dom.button("Rename",()=>draw("rename")),Dom.button("Delete",()=>draw("delete"))]),note)}
      function drawRename(caption){const input=Dom.el("input",{type:"text",maxlength:"120","aria-label":"New project title"});input.value=project.title;async function save(){try{await Api.renameProject(project.id,input.value,project.updated_at);await loadList()}catch(error){showNote(error)}}input.addEventListener("keydown",e=>{if(e.key==="Enter")save();if(e.key==="Escape")draw("view")});caption.append(input,Dom.el("div",{class:"row"},[Dom.button("Save",save,"primary"),Dom.button("Cancel",()=>draw("view"))]),note);input.focus();input.select()}
      function drawDelete(caption){async function confirmDelete(){try{await Api.deleteProject(project.id);await loadList()}catch(error){showNote(error)}}caption.append(Dom.el("p",{class:"warning",text:"Delete this project and everything in it? This cannot be undone."}),Dom.el("div",{class:"row"},[Dom.button("Delete project",confirmDelete,"danger"),Dom.button("Cancel",()=>draw("view"))]),note)}
      draw("view");return card;
    }
  }
};
