/* No API secret or publishable key is ever required in the customer browser. */
(() => {
 const form = document.getElementById('quote-form');
 if (!form || !window.fetch || !window.FormData || !window.XMLHttpRequest) return;
 const status = document.getElementById('upload-status');
 const progress = document.getElementById('upload-progress');
 const button = document.getElementById('quote-submit');
 function say(message, isError=false) {
   status.hidden = false; status.textContent = message;
   status.classList.toggle('upload-error', isError);
 }
 function request(url, data) {
   return fetch(url, {method:'POST', body:data, credentials:'same-origin', headers:{'Accept':'application/json'}})
    .then(async r => {let obj = await r.json().catch(()=>({})); if (!r.ok) throw new Error(obj.error || 'Request failed.'); return obj;});
 }
 function uploadSigned(url, file) {
   return new Promise((resolve,reject) => {
     const xhr = new XMLHttpRequest();
     xhr.open('PUT', url);
     xhr.upload.onprogress = e => {
       if (e.lengthComputable) {const pct=Math.round(e.loaded/e.total*100); progress.value=pct; say(`Uploading privately to Supabase: ${pct}%`);}
     };
     xhr.onload = () => (xhr.status >= 200 && xhr.status < 300) ? resolve() : reject(new Error('Storage rejected this upload. Check your Supabase bucket size limit and try again.'));
     xhr.onerror = () => reject(new Error('Upload connection failed. Please try again.'));
     const body = new FormData();
     body.append('cacheControl', '3600');
     body.append('', file);
     xhr.send(body);
   });
 }
 form.addEventListener('submit', async event => {
   event.preventDefault();
   if (!form.reportValidity()) return;
   const file = form.querySelector('input[type=file]').files[0];
   const maxMB = Number(form.dataset.maxMb || 100);
   if (!file || file.size < 1 || file.size > maxMB*1024*1024) {say(`Select a non-empty file smaller than ${maxMB} MB.`, true); return;}
   button.disabled = true; progress.hidden = false; progress.value=0;
   try {
     const fields = new FormData(form); fields.delete('file');
     const begin = new FormData();
     for (const [key,value] of fields) begin.append(key,value);
     begin.append('upload_name', file.name);
     begin.append('upload_size', String(file.size));
     say('Preparing your secure upload…');
     const init = await request('/api/quote/start', begin);
     await uploadSigned(init.upload_url, file);
     say('Upload complete. Saving your quotation request…');
     const result = await request('/api/quote/finish', fields);
     window.location.assign(result.redirect);
   } catch (error) {
     say(error.message || 'Something went wrong. Please try again.', true);
     button.disabled = false;
   }
 });
})();
