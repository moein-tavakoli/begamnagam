export function newerVersion(candidate: unknown, current: string): candidate is string {
  if(typeof candidate!=="string" || !/^\d+\.\d+\.\d+$/.test(candidate))return false;
  const next=candidate.split('.').map(Number),old=current.split('.').map(Number);
  for(let i=0;i<3;i++)if(next[i]!==old[i])return next[i]>old[i];
  return false;
}
