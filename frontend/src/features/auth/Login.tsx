import { useState } from 'react';
import type { FormEvent } from 'react';
import { login, API_BASE_URL } from '../../api/client';

export function Login({onLogin}:{onLogin:(u:any)=>void}) {
  const [username,setUsername]=useState('');
  const [password,setPassword]=useState('');
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  async function submit(e:FormEvent){
    e.preventDefault(); setError(''); setBusy(true);
    try { onLogin(await login(username.trim(),password)); }
    catch(err){ setError(err instanceof Error?err.message:'Login failed'); }
    finally { setBusy(false); }
  }
  return <div className="login-page">
    <div className="login-decoration"><div className="login-orbit one"/><div className="login-orbit two"/><div className="login-grid"/></div>
    <div className="login-brand-panel">
      <div className="brand-mark">LT</div>
      <span className="eyebrow">LOVELY TECH</span>
      <h1>Run the shop.<br/><em>Simply.</em></h1>
      <p>Sales, stock, repairs, warranty and day-end control in one offline-first POS.</p>
      <div className="login-feature-list"><span>✓ Branch-aware inventory</span><span>✓ Atomic sales & payments</span><span>✓ Audit-ready history</span></div>
    </div>
    <form className="login-card glass-card" onSubmit={submit}>
      <div className="login-card-head"><div><span className="eyebrow">SECURE SIGN IN</span><h2>Welcome back</h2><p>Use your Lovely Tech account to continue.</p></div><span className="secure-dot">●</span></div>
      <label>Username<input autoFocus autoComplete="username" placeholder="Enter username" value={username} onChange={e=>setUsername(e.target.value)}/></label>
      <label>Password<input type="password" autoComplete="current-password" placeholder="Enter password" value={password} onChange={e=>setPassword(e.target.value)}/></label>
      {error&&<div className="error login-error">{error}</div>}
      <button aria-label="Login" className="login-submit" disabled={busy||!username.trim()||!password}>{busy?'Signing in…':'Sign in to POS'} <span>→</span></button>
      <div className="login-footer"><span>Server</span><b>{API_BASE_URL}</b></div>
    </form>
  </div>
}
