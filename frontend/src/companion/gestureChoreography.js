// Authored task-space arcs relative to chest, in metres for a reference adult.
// Keyframes separate preparation, stroke, hold and recovery. These are original
// MedGuard assets; no third-party motion/model assets are redistributed.
const paths={
 greeting:[[.145,-.06,.16],[.145,.075,.20],[.155,.082,.20],[.139,.078,.20],[.15,.075,.20],[.14,-.04,.17]],
 explain:[[.13,-.07,.16],[.16,.02,.19],[.20,.035,.23],[.19,.02,.22],[.17,.0,.21],[.13,-.06,.16]],
 invite:[[.13,-.05,.17],[.16,.0,.19],[.19,.015,.25],[.19,.01,.24],[.17,-.01,.22],[.13,-.06,.17]],
 reassure:[[.12,-.05,.15],[.15,-.01,.19],[.16,.005,.22],[.16,.005,.22],[.14,-.02,.20],[.12,-.07,.15]],
 caution:[[.13,-.04,.16],[.15,.065,.19],[.16,.075,.20],[.16,.075,.20],[.15,.04,.19],[.13,-.05,.17]],
 enumerate:[[.13,-.04,.16],[.15,.06,.19],[.17,.075,.21],[.17,.075,.21],[.15,.045,.20],[.13,-.05,.17]],
 compare:[[.14,-.06,.17],[.18,.01,.21],[.22,.03,.23],[.21,.02,.23],[.18,.0,.21],[.14,-.06,.17]],
 guide:[[.13,-.06,.17],[.16,.015,.20],[.20,.035,.23],[.19,.025,.23],[.16,.0,.21],[.13,-.06,.17]],
};
const times=[0,.22,.38,.53,.70,1];
const ease=t=>t*t*t*(t*(t*6-15)+10);
export function choreograph(intent,phase,duration,variant={}) {
 const points=paths[intent]||paths.explain,t=Math.max(0,Math.min(1,phase/duration));
 let i=0;while(i<times.length-2&&t>times[i+1])i++;
 const a=ease(Math.max(0,Math.min(1,(t-times[i])/(times[i+1]-times[i]))));
 const point=points[i].map((v,k)=>v+(points[i+1][k]-v)*a);
 if(intent==='greeting')point[0]+=Math.sin(Math.max(0,t-.25)*Math.PI*8)*Math.sin(Math.PI*Math.max(0,Math.min(1,(t-.25)/.45)))**2*.008;
 if(variant.id==='hand-near-heart')return [.065,point[1]*.4+.025,.17];
 // Differences in range preserve the meaning of the gesture.
 const range=(variant.id?.includes('small')||variant.id?.includes('gentle')) ? .88 : variant.id?.includes('spatial') ? 1.08 : 1;
 return [point[0]*range,point[1],point[2]];
}
