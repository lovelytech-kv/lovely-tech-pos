import { useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../../api/client';

/** Shown instead of the POS when an Admin has reset this user's password (must_change_password). */
export function ChangePassword({user,onDone,onLogout}:{user:any;onDone:(u:any)=>void;onLogout:()=>void}) {
  const [current,setCurrent]=useState('');
  const [next,setNext]=useState('');
  const [again,setAgain]=useState('');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  async function submit(e:FormEvent){
    e.preventDefault(); setError('');
    if(next.length<10) return setError('New password must be at least 10 characters.');
    if(next!==again) return setError('The two new passwords do not match.');
    if(next===current) return setError('New password must be different from the temporary password.');
    try{
      setBusy(true);
      await api('/auth/change-password',{method:'POST',body:JSON.stringify({current_password:current,new_password:next})});
      const updated={...user,must_change_password:false};
      localStorage.setItem('ltpos_user',JSON.stringify(updated));
      onDone(updated);
    }catch(err){ setError(err instanceof Error?err.message:'Could not change password'); }
    finally{ setBusy(false); }
  }
  return <div className="login-page"><form className="login-card glass-card" onSubmit={submit}>
    <div className="login-card-head"><div><span className="eyebrow">PASSWORD CHANGE REQUIRED</span><h2>Set a new password</h2><p>{user.display_name||user.username}, an Admin reset your password. Choose your own password to continue.</p></div></div>
    <label>Temporary password<input type="password" autoComplete="current-password" placeholder="Temporary password" value={current} onChange={e=>setCurrent(e.target.value)}/></label>
    <label>New password<input type="password" autoComplete="new-password" placeholder="New password (min 10 characters)" value={next} onChange={e=>setNext(e.target.value)}/></label>
    <label>Repeat new password<input type="password" autoComplete="new-password" placeholder="Repeat new password" value={again} onChange={e=>setAgain(e.target.value)}/></label>
    {error&&<div className="error login-error" role="alert">{error}</div>}
    <button aria-label="Change password" className="login-submit" disabled={busy||!current||!next||!again}>{busy?'Saving…':'Save new password'} <span>→</span></button>
    <button type="button" className="link-button" onClick={onLogout}>Sign out</button>
  </form></div>
}
