// frontend/src/pages/VerifyEmail.tsx
// 驗證信裡的連結會開到這頁（/verify-email?token=...），由這裡呼叫後端完成驗證。
import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { isAxiosError } from 'axios';
import { api } from '../api/client';
import Sidebar from '../components/Sidebar';
import '../styles/Login.css';

type Status = 'verifying' | 'success' | 'failed';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [status, setStatus] = useState<Status>(token ? 'verifying' : 'failed');
  const [message, setMessage] = useState(token ? '驗證中…' : '驗證連結不完整，請重新點擊信中的連結');

  // 連結失效時可以直接在這頁重寄
  const [useremail, setUseremail] = useState('');
  const [resendMessage, setResendMessage] = useState('');
  const [resending, setResending] = useState(false);

  // token 只能用一次：StrictMode 下 effect 會跑兩次，第二次會變成「已失效」
  const requestedRef = useRef(false);

  useEffect(() => {
    if (!token || requestedRef.current) return;
    requestedRef.current = true;
    api.post<{ message: string }>('/verify-registration/', { token })
      .then(res => {
        setStatus('success');
        setMessage(res.data.message);
      })
      .catch(err => {
        setStatus('failed');
        const error = isAxiosError<{ error?: string }>(err) ? err.response?.data?.error : undefined;
        setMessage(error || '驗證失敗，請稍後再試');
      });
  }, [token]);

  const resend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!useremail.trim()) {
      setResendMessage('請輸入註冊時使用的 email');
      return;
    }
    setResending(true);
    try {
      const res = await api.post<{ message: string }>('/resend-verification/', { useremail: useremail.trim() });
      setResendMessage(res.data.message);
    } catch (err) {
      setResendMessage(
        isAxiosError(err) && err.response?.status === 429
          ? '重寄太多次了，請稍後再試'
          : '重寄失敗，請稍後再試'
      );
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="outercontainer">
      <div className="submitForm-container">
        <h2 className="loginText">信箱驗證</h2>
        <p>{message}</p>

        {status === 'success' && (
          <Link to="/login">前往登入</Link>
        )}

        {status === 'failed' && (
          <form onSubmit={resend}>
            <p>需要新的驗證信嗎？輸入註冊時的 email，我們會重新寄一封。</p>
            <input
              className="accountTextField"
              type="email"
              placeholder="email"
              value={useremail}
              onChange={(e) => setUseremail(e.target.value)}
            />
            <button className="resend-button" type="submit" disabled={resending}>
              {resending ? '寄送中…' : '重寄驗證信'}
            </button>
            {resendMessage && <p>{resendMessage}</p>}
          </form>
        )}
      </div>
      <Sidebar />
    </div>
  );
}
