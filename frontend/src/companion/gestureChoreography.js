// Authored task-space arcs relative to chest, in metres for a reference adult.
// Keyframes separate preparation, stroke, hold and recovery. These are original
// MedGuard assets; no third-party motion/model assets are redistributed.
const paths={
 greeting:[[.145,-.06,.16],[.145,.075,.20],[.155,.082,.20],[.139,.078,.20],[.15,.075,.20],[.14,-.04,.17]],
 explain:[[.15,-.06,.17],[.20,.025,.22],[.27,.045,.26],[.25,.035,.25],[.20,.01,.22],[.15,-.05,.17]],
 invite:[[.15,-.05,.17],[.20,.01,.22],[.26,.025,.27],[.25,.02,.26],[.20,0,.22],[.15,-.05,.17]],
 reassure:[[.14,-.05,.16],[.17,-.01,.21],[.21,.015,.24],[.21,.015,.24],[.17,-.015,.22],[.14,-.06,.16]],
 caution:[[.15,-.04,.17],[.18,.065,.21],[.21,.085,.23],[.21,.085,.23],[.18,.05,.21],[.15,-.04,.17]],
 enumerate:[[.15,-.04,.17],[.18,.06,.21],[.22,.08,.23],[.22,.08,.23],[.18,.05,.22],[.15,-.05,.17]],
 compare:[[.16,-.06,.17],[.22,.02,.23],[.28,.04,.26],[.27,.03,.25],[.21,.005,.23],[.16,-.05,.17]],
 guide:[[.15,-.06,.17],[.20,.02,.22],[.26,.045,.26],[.25,.035,.25],[.20,.01,.22],[.15,-.05,.17]],
};
const times=[0,.22,.38,.53,.70,1];
const ease=t=>t*t*t*(t*(t*6-15)+10);
export function choreograph(intent,phase,duration,variant={}) {
 const points=paths[intent]||paths.explain,t=Math.max(0,Math.min(1,phase/duration));
 let i=0;while(i<times.length-2&&t>times[i+1])i++;
 const a=ease(Math.max(0,Math.min(1,(t-times[i])/(times[i+1]-times[i]))));
 const point=points[i].map((v,k)=>v+(points[i+1][k]-v)*a);
 if(intent==='greeting')point[0]+=Math.sin(Math.max(0,t-.25)*Math.PI*3.2)*Math.sin(Math.PI*Math.max(0,Math.min(1,(t-.25)/.50)))**2*.005;
 if(variant.id==='hand-near-heart')return [.065,point[1]*.4+.025,.17];
 // Differences in range preserve the meaning of the gesture.
 const range=(variant.id?.includes('small')||variant.id?.includes('gentle')) ? .88 : variant.id?.includes('spatial') ? 1.15 : variant.id==='two-sides' ? 1.12 : 1;
 return [point[0]*range,point[1],point[2]];
}
