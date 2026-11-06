
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.1/build/three.module.js';
const canvas=document.querySelector('#gear-canvas');
if(canvas){
const scene=new THREE.Scene();
const camera=new THREE.PerspectiveCamera(38,1,.1,100);
camera.position.set(0,3.8,9.8);
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true,powerPreference:'low-power'});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.8));
renderer.outputColorSpace=THREE.SRGBColorSpace;
const metal=new THREE.MeshStandardMaterial({color:0x8399a5,metalness:.76,roughness:.28});
const dark=new THREE.MeshStandardMaterial({color:0x283e50,metalness:.7,roughness:.33});
const cyan=new THREE.MeshStandardMaterial({color:0x36c9d7,metalness:.55,roughness:.25});
scene.add(new THREE.HemisphereLight(0x9cdbff,0x101c2c,2.0));
const key=new THREE.DirectionalLight(0xffffff,4);key.position.set(3,6,7);scene.add(key);
const rim=new THREE.PointLight(0x2ac9e6,80);rim.position.set(-4,1,-3);scene.add(rim);
const assembly=new THREE.Group();scene.add(assembly);
function cylinder(radius,depth,material,x=0,y=0,z=0){
 const mesh=new THREE.Mesh(new THREE.CylinderGeometry(radius,radius,depth,64),material);
 mesh.position.set(x,y,z);assembly.add(mesh);return mesh;
}
function ring(radius,tube,material,y){
 const mesh=new THREE.Mesh(new THREE.TorusGeometry(radius,tube,12,96),material);
 mesh.rotation.x=Math.PI/2;mesh.position.y=y;assembly.add(mesh);return mesh;
}
function gear(radius,teeth,material,x,z,y=.1){
 const group=new THREE.Group();group.position.set(x,y,z);assembly.add(group);
 const body=new THREE.Mesh(new THREE.CylinderGeometry(radius,radius,.32,64),material);group.add(body);
 const toothGeo=new THREE.BoxGeometry(.25,.32,.27);
 for(let i=0;i<teeth;i++){const a=i*2*Math.PI/teeth;const tooth=new THREE.Mesh(toothGeo,material);tooth.position.set(Math.cos(a)*radius,0,Math.sin(a)*radius);tooth.rotation.y=-a;group.add(tooth)}
 const hub=new THREE.Mesh(new THREE.CylinderGeometry(radius*.25,radius*.25,.42,32),dark);group.add(hub);
 return group;
}
cylinder(3.12,.16,dark,0,-.33,0);
ring(3.05,.16,metal,.04);ring(2.62,.12,cyan,.07);
gear(.92,16,metal,0,0,.14);
const planets=[];
for(let i=0;i<3;i++){const a=i*2*Math.PI/3;planets.push(gear(.62,12,metal,Math.cos(a)*1.82,Math.sin(a)*1.82,.13))}
for(let i=0;i<3;i++){const a=i*2*Math.PI/3;cylinder(.12,.42,cyan,Math.cos(a)*1.82,.42,Math.sin(a)*1.82)}
assembly.rotation.x=.25;
let dragging=false,lastX=0,lastY=0,angle=.35,tilt=.3,zoom=9.8;
canvas.addEventListener('pointerdown',e=>{dragging=true;lastX=e.clientX;lastY=e.clientY;canvas.setPointerCapture(e.pointerId)});
canvas.addEventListener('pointermove',e=>{if(!dragging)return;angle+=(e.clientX-lastX)*.008;tilt=Math.max(-.55,Math.min(.85,tilt+(e.clientY-lastY)*.006));lastX=e.clientX;lastY=e.clientY});
canvas.addEventListener('pointerup',()=>dragging=false);
canvas.addEventListener('pointercancel',()=>dragging=false);
canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(6.5,Math.min(14,zoom+e.deltaY*.01))},{passive:false});
function resize(){const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix()}
new ResizeObserver(resize).observe(canvas);resize();
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
let last=0;
function frame(t){requestAnimationFrame(frame);if(!document.hidden&&canvas.getBoundingClientRect().bottom>0){if(!dragging&&!reduced)angle+=(t-last)*.00008;assembly.rotation.y=angle;assembly.rotation.x=tilt;camera.position.set(0,3.4,zoom);camera.lookAt(0,0,0);renderer.render(scene,camera)}last=t}
requestAnimationFrame(frame);
}
