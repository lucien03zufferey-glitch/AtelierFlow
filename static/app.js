const menuButton=document.querySelector('#menuButton');
menuButton?.addEventListener('click',()=>{const sidebar=document.querySelector('.sidebar');sidebar?.classList.toggle('open');menuButton.setAttribute('aria-expanded',String(sidebar?.classList.contains('open')))});
document.querySelectorAll('.sidebar nav a').forEach(a=>a.addEventListener('click',()=>document.querySelector('.sidebar')?.classList.remove('open')));
document.querySelectorAll('[data-modal-open]').forEach(b=>b.addEventListener('click',()=>document.getElementById(b.dataset.modalOpen)?.showModal()));
document.querySelectorAll('[data-modal-close]').forEach(b=>b.addEventListener('click',()=>b.closest('dialog')?.close()));
document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target===d)d.close()}));

const messages=document.querySelector('#messages');
const messageForm=document.querySelector('#messageForm');
if(messages&&messageForm){
  const projectId=messages.dataset.project;
  const esc=s=>String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  let last='';
  async function refreshMessages(force=false){
    try{
      const response=await fetch(`/api/projects/${projectId}/messages`);
      if(!response.ok)return;
      const data=await response.json();
      const signature=JSON.stringify(data);
      if(force||signature!==last){
        messages.innerHTML=data.map(m=>`<div class="message"><span class="avatar" style="--avatar:${esc(m.color)}">${esc(m.initials)}</span><div><div class="message-meta"><strong>${esc(m.author_name)}</strong><time>${esc(m.created_at.slice(5,16))}</time></div><p>${esc(m.body)}</p></div></div>`).join('');
        messages.scrollTop=messages.scrollHeight;last=signature;
      }
    }catch(_){/* La prochaine actualisation réessaiera. */}
  }
  messageForm.addEventListener('submit',async e=>{
    e.preventDefault();const input=document.querySelector('#messageInput');const body=input.value.trim();if(!body)return;
    const button=messageForm.querySelector('button');button.disabled=true;
    try{const r=await fetch(`/api/projects/${projectId}/messages`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({body})});if(r.ok){input.value='';await refreshMessages(true)}else{alert('Le message n’a pas pu être envoyé. Réessayez.')}}catch(_){alert('Connexion interrompue. Réessayez.')}finally{button.disabled=false;input.focus()}
  });
  refreshMessages(true);setInterval(refreshMessages,4000);
}
