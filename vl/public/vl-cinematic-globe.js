(()=>{
const c=document.getElementById('vl-globe'); if(!c) return;
const ctx=c.getContext('2d',{alpha:true}); let w=0,h=0,dpr=1,raf=0,rot=0,last=0;
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const lowPower=matchMedia('(max-width: 700px)').matches || (navigator.hardwareConcurrency&&navigator.hardwareConcurrency<=4);
const targetFrame=lowPower?33:16;
const DEG=Math.PI/180;
const stars=[]; const lights=[];
function rnd(i){const v=Math.sin(i*991.73)*43758.5453;return v-Math.floor(v)}
for(let i=0;i<(lowPower?80:150);i++) stars.push([rnd(i+3),rnd(i+203),.35+1.45*rnd(i+403),.22+.7*rnd(i+603)]);
for(let i=0;i<(lowPower?280:650);i++) lights.push([rnd(i+901)*360-180,rnd(i+1201)*120-60,.35+1.2*rnd(i+1501),rnd(i+1801)]);
const land=[
[[-168,72],[-150,70],[-139,60],[-124,52],[-122,42],[-111,31],[-101,23],[-91,19],[-84,23],[-81,30],[-76,37],[-66,45],[-59,52],[-64,60],[-78,70],[-105,75],[-135,73]],
[[-81,12],[-74,7],[-70,-4],[-67,-16],[-62,-27],[-57,-38],[-64,-52],[-73,-48],[-78,-35],[-80,-18]],
[[-17,37],[-5,35],[10,37],[25,32],[34,31],[43,12],[49,-12],[39,-27],[28,-35],[13,-35],[2,-28],[-7,-12],[-15,5],[-17,20]],
[[-10,36],[2,44],[18,55],[34,60],[52,55],[67,58],[83,55],[100,50],[117,50],[132,44],[145,51],[158,58],[171,64],[170,50],[151,38],[130,28],[114,20],[104,10],[92,7],[81,18],[69,22],[56,27],[44,32],[33,39],[22,42],[12,42],[2,40]],
[[35,31],[48,30],[58,24],[67,23],[77,8],[90,6],[102,13],[112,20],[121,31],[131,38],[141,42],[146,34],[137,27],[125,18],[113,8],[104,1],[99,-7],[88,-4],[77,7],[67,16],[56,21],[45,24]],
[[112,-11],[121,-17],[132,-15],[142,-18],[153,-27],[151,-39],[139,-44],[126,-40],[116,-33]],
[[-73,83],[-49,82],[-20,74],[-33,65],[-47,60],[-58,63],[-67,72]],
[[-180,-64],[-145,-67],[-110,-69],[-75,-70],[-40,-69],[-5,-71],[30,-69],[65,-70],[100,-68],[140,-66],[180,-64],[180,-89],[-180,-89]]
];
const hubs=[[2,51],[13,52],[37,55],[31,30],[55,25],[77,28],[103,1],[121,14],[139,36],[151,-33],[-74,40],[-118,34],[-99,19],[-46,-23],[18,-34]];
const arcs=[[2,51,103,1],[-74,40,2,51],[-118,34,139,36],[77,28,103,1],[31,30,55,25],[151,-33,103,1],[-46,-23,2,51],[18,-34,55,25]];
function resize(){dpr=Math.min(devicePixelRatio||1,lowPower?1.35:2);w=c.clientWidth;h=c.clientHeight;c.width=Math.max(1,Math.floor(w*dpr));c.height=Math.max(1,Math.floor(h*dpr));ctx.setTransform(dpr,0,0,dpr,0,0);draw(performance.now(),true)}
function project(lon,lat,R,cx,cy){const a=(lon*DEG)+rot,b=lat*DEG,cl=Math.cos(b),x=cl*Math.sin(a),y=Math.sin(b),z=cl*Math.cos(a);return[cx+x*R,cy-y*R,z]}
function globeMetrics(){const mobile=w<700;const R=Math.min(h*(mobile?.46:.73),w*(mobile?.47:.34));return {R,cx:w*(mobile?.68:.68),cy:h*(mobile?.36:.57)}}
function pathPolygon(poly,R,cx,cy){ctx.beginPath();let started=false;for(const q of poly){const p=project(q[0],q[1],R,cx,cy);if(p[2]>.01){if(!started){ctx.moveTo(p[0],p[1]);started=true}else ctx.lineTo(p[0],p[1]);}else started=false;}return started}
function drawGrid(R,cx,cy){ctx.lineWidth=.55;for(let lat=-60;lat<=60;lat+=15){ctx.beginPath();let s=false;for(let lon=-180;lon<=180;lon+=4){const p=project(lon,lat,R,cx,cy);if(p[2]>0){s?ctx.lineTo(p[0],p[1]):(ctx.moveTo(p[0],p[1]),s=true)}else s=false}ctx.strokeStyle='rgba(93,164,255,.14)';ctx.stroke()}for(let lon=-180;lon<180;lon+=20){ctx.beginPath();let s=false;for(let lat=-85;lat<=85;lat+=3){const p=project(lon,lat,R,cx,cy);if(p[2]>0){s?ctx.lineTo(p[0],p[1]):(ctx.moveTo(p[0],p[1]),s=true)}else s=false}ctx.strokeStyle='rgba(93,164,255,.12)';ctx.stroke()}}
function drawLand(R,cx,cy){ctx.save();ctx.beginPath();ctx.arc(cx,cy,R,0,Math.PI*2);ctx.clip();for(const poly of land){pathPolygon(poly,R,cx,cy);ctx.fillStyle='rgba(52,112,172,.92)';ctx.fill();ctx.strokeStyle='rgba(176,218,255,.2)';ctx.lineWidth=.7;ctx.stroke()}for(const l of lights){const p=project(l[0],l[1],R,cx,cy);if(p[2]<=.05)continue;let near=false;for(const poly of land){for(const q of poly){if(Math.abs(q[0]-l[0])<18&&Math.abs(q[1]-l[1])<13){near=true;break}}if(near)break}if(!near||l[3]<.44)continue;ctx.globalAlpha=.16+.5*p[2];ctx.fillStyle=l[3]>.82?'#ffe8b0':'#9bd0ff';ctx.beginPath();ctx.arc(p[0],p[1],l[2],0,Math.PI*2);ctx.fill()}ctx.globalAlpha=1;ctx.restore()}
function drawArcs(R,cx,cy){for(const a of arcs){const A=project(a[0],a[1],R,cx,cy),B=project(a[2],a[3],R,cx,cy);if(A[2]<.06||B[2]<.06)continue;const mx=(A[0]+B[0])/2,my=(A[1]+B[1])/2-R*.17;ctx.strokeStyle='rgba(80,173,255,.38)';ctx.lineWidth=.8;ctx.beginPath();ctx.moveTo(A[0],A[1]);ctx.quadraticCurveTo(mx,my,B[0],B[1]);ctx.stroke()}for(const p0 of hubs){const p=project(p0[0],p0[1],R,cx,cy);if(p[2]<=.08)continue;ctx.fillStyle='rgba(205,233,255,.95)';ctx.beginPath();ctx.arc(p[0],p[1],1.8,0,Math.PI*2);ctx.fill()}}
function draw(now,force=false){if(!force&&now-last<targetFrame){raf=requestAnimationFrame(draw);return}last=now;ctx.clearRect(0,0,w,h);const {R,cx,cy}=globeMetrics();const wash=ctx.createRadialGradient(w*.72,h*.12,0,w*.72,h*.12,Math.max(w,h)*.74);wash.addColorStop(0,'rgba(31,103,255,.17)');wash.addColorStop(.5,'rgba(7,30,74,.08)');wash.addColorStop(1,'rgba(0,0,0,0)');ctx.fillStyle=wash;ctx.fillRect(0,0,w,h);
for(const s of stars){ctx.globalAlpha=s[3]*(.8+.2*Math.sin(now*.001+s[0]*14));ctx.fillStyle='#c8e1ff';ctx.beginPath();ctx.arc(s[0]*w,s[1]*h,s[2],0,Math.PI*2);ctx.fill()}ctx.globalAlpha=1;
const halo=ctx.createRadialGradient(cx,cy,R*.72,cx,cy,R*1.25);halo.addColorStop(0,'rgba(0,76,190,.04)');halo.addColorStop(.78,'rgba(38,132,255,.2)');halo.addColorStop(1,'rgba(56,135,255,0)');ctx.fillStyle=halo;ctx.beginPath();ctx.arc(cx,cy,R*1.25,0,Math.PI*2);ctx.fill();
const ocean=ctx.createRadialGradient(cx-R*.34,cy-R*.38,R*.12,cx,cy,R);ocean.addColorStop(0,'#1f65b7');ocean.addColorStop(.42,'#0b3b7d');ocean.addColorStop(.78,'#062653');ocean.addColorStop(1,'#021329');ctx.fillStyle=ocean;ctx.beginPath();ctx.arc(cx,cy,R,0,Math.PI*2);ctx.fill();
drawLand(R,cx,cy);drawGrid(R,cx,cy);drawArcs(R,cx,cy);
const shade=ctx.createLinearGradient(cx-R,cy,cx+R,cy);shade.addColorStop(0,'rgba(0,5,15,.5)');shade.addColorStop(.46,'rgba(0,0,0,0)');shade.addColorStop(1,'rgba(66,160,255,.1)');ctx.fillStyle=shade;ctx.beginPath();ctx.arc(cx,cy,R,0,Math.PI*2);ctx.fill();
const rim=ctx.createRadialGradient(cx-R*.2,cy-R*.2,R*.7,cx,cy,R*1.02);rim.addColorStop(.78,'rgba(255,255,255,0)');rim.addColorStop(.95,'rgba(86,177,255,.25)');rim.addColorStop(1,'rgba(177,221,255,.78)');ctx.fillStyle=rim;ctx.beginPath();ctx.arc(cx,cy,R*1.01,0,Math.PI*2);ctx.fill();
const sun=ctx.createRadialGradient(cx+R*.73,cy-R*.68,0,cx+R*.73,cy-R*.68,R*.33);sun.addColorStop(0,'rgba(255,255,255,.95)');sun.addColorStop(.09,'rgba(180,218,255,.78)');sun.addColorStop(1,'rgba(48,139,255,0)');ctx.fillStyle=sun;ctx.beginPath();ctx.arc(cx+R*.73,cy-R*.68,R*.33,0,Math.PI*2);ctx.fill();
if(!reduced) rot+=(lowPower?.00115:.00165); if(!reduced&&!document.hidden) raf=requestAnimationFrame(draw); else raf=0}
const ro=typeof ResizeObserver!=='undefined'?new ResizeObserver(resize):null;if(ro)ro.observe(c);else addEventListener('resize',resize);resize();
document.addEventListener('visibilitychange',()=>{if(document.hidden){if(raf)cancelAnimationFrame(raf);raf=0}else if(!reduced&&!raf){last=0;raf=requestAnimationFrame(draw)}});
})();