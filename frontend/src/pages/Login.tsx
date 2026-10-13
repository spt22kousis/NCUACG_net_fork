import { useState ,useEffect} from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/auth';
import type { User } from '../contexts/auth';
import Sidebar from '../components/Sidebar';
import { isAxiosError } from 'axios';
import { api, clearTokens, setTokens } from '../api/client';
import '../styles/Login.css';

interface CaptchaResponse {
  captcha_key: string;
  captcha_image_url: string;
}

export default function Login() {
  const navigate = useNavigate();
  const [useremail, setUseremail] = useState('');
  const [password, setPassword] = useState('');
  const { setUser } = useAuth(); // 從 Context 取得 setUser
  const [message, setMessage] = useState('')
  const [captcha, setCaptcha] = useState<CaptchaResponse | null>(null);
  const [captchaInput, setCaptchaInput] = useState(''); // 使用者輸入
  // 帳密正確但信箱還沒驗證：顯示「重寄驗證信」按鈕
  const [unverified, setUnverified] = useState(false);
  const [resending, setResending] = useState(false);
  const loadCaptcha = async () => {
    try {
      const res = await api.get<CaptchaResponse>("/get-captcha/");
      setCaptcha(res.data);
      setCaptchaInput('');
      console.log(res.data)
    } catch (err) {
      console.error("Failed to load captcha:", err);
    }
  };

  useEffect(() => {
    loadCaptcha();
  }, []);
  const handleLogin = async (e: React.FormEvent) => {
  e.preventDefault();
  if (!useremail || !password){
      setMessage("你的帳號密碼咧?");
      return;
    }
   setUnverified(false);
   // 登入成功、token 已存起來之後，若 /me/ 失敗要把 token 收回，避免「畫面說失敗、其實半登入」
   let tokensSaved = false;
   try {
    // 登入
    const loginRes = await api.post(
      '/login/',
      {
        useremail,
        password,
        captcha_key: captcha?.captcha_key,
        captcha_value: captchaInput
      }
    );
    setMessage(loginRes.data.message);
    const accessToken = loginRes.data.access;
    const refreshToken = loginRes.data.refresh;

    // 交給 api client 統一保管；之後每個請求的 Authorization 都由攔截器帶上
    setTokens(accessToken, refreshToken);
    tokensSaved = true;

    // 成功 → 抓 /api/me/ 更新 Context
    const meRes = await api.get<User>('/me/');
    setUser(meRes.data);
    // 登入成功後延遲 1 秒跳轉到首頁
    setTimeout(() => {
      navigate('/');
    }, 1000);
  } catch (err) {
    // 驗證碼是一次性的（不論答對答錯，後端都會作廢），失敗後一定要換一張新的，
    // 否則使用者照著畫面上的舊圖重試只會一直得到「驗證碼已失效」
    loadCaptcha();

    if (tokensSaved) {
      clearTokens();
      setMessage('讀取個人資料失敗，請稍後重新登入');
      return;
    }

    // 後端回 DRF 標準格式：{"captcha": ["驗證碼錯誤"]}、{"useremail": ["帳號或密碼錯誤"]}
    const data: unknown = isAxiosError(err) ? err.response?.data : undefined;
    if (data && typeof data === 'object') {
      if ('unverified' in data) setUnverified(true);
      const firstError = Object.values(data)[0];
      if (Array.isArray(firstError) && firstError.length > 0) {
        setMessage(String(firstError[0]));
        return;
      }
      if (typeof firstError === 'string') {
        setMessage(firstError);
        return;
      }
    }
    setMessage('登入失敗，請稍後再試');
  }
  }
  const resendVerification = async () => {
    setResending(true);
    try {
      const res = await api.post<{ message: string }>('/resend-verification/', { useremail });
      setMessage(res.data.message);
      setUnverified(false);
    } catch (err) {
      setMessage(
        isAxiosError(err) && err.response?.status === 429
          ? '重寄太多次了，請稍後再試'
          : '重寄失敗，請稍後再試'
      );
    } finally {
      setResending(false);
    }
  };
  const [showPassword, setShowPassword] = useState(false);
  return (

  <div className='outercontainer'>
  
  <div className='submitForm-container'>
  <h2 className='loginText'>登入</h2>
   {captcha ? (
        <div>
          <img
            src={captcha.captcha_image_url}
            alt="captcha"
            className="border rounded"
          />
          <button
            onClick={loadCaptcha}
            className="captcha-refresh"
          >
            Refresh
          </button>
        </div>
      ) : (
        <p>Loading captcha...</p>
      )}
  <form onSubmit={handleLogin} >
    <input
      className='accountTextField'
      type="text"
      placeholder="帳號"
      value={useremail}
      onChange={(e) => setUseremail(e.target.value)}
    />
    <input
      className='passwordTextField'
      type={showPassword ? "text" : "password"}
      placeholder="密碼"
      value={password}
      onChange={(e) => setPassword(e.target.value)}
    />
    <input
      className='accountTextField'
      type="text"
      placeholder="驗證碼"
      value={captchaInput}
      onChange={(e) => setCaptchaInput(e.target.value)}
    />
    <button
        type="button"
        className="toggle-btn"
        onClick={() => setShowPassword(!showPassword)}
      >
        <img
          src={showPassword ?  "/images/eye.png":"/images/eye_off.png"}
          alt="toggle password"
          className="eye-icon"
        />
      </button>
    <p>{message}</p>
    {unverified && (
      <button type="button" className="resend-button" onClick={resendVerification} disabled={resending}>
        {resending ? '寄送中…' : '重寄驗證信'}
      </button>
    )}
    <button className='submitButton' type="submit">登入</button>
  </form>

  <div>
    <a href="/forget-password">忘記密碼？</a>
    <a href="/register">註冊帳號</a>
  </div>

  <hr />

  <div>
    <p>其他登入方式</p>
    {/* 中央大學 Portal 登入尚未串接 */}
    <button type="button" className='portal_submit_btn' disabled title="即將推出">
      portal 登入（即將推出）
    </button>
  </div>
</div>
  <Sidebar />
</div>
  );
}
