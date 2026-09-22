import { useState ,useEffect} from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import type { User } from '../contexts/AuthContext';
import Sidebar from '../components/Sidebar';
import { isAxiosError } from 'axios';
import { api, setTokens } from '../api/client';
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

    // 後端回 DRF 標準格式：{"captcha": ["驗證碼錯誤"]}、{"useremail": ["帳號或密碼錯誤"]}
    const data: unknown = isAxiosError(err) ? err.response?.data : undefined;
    if (data && typeof data === 'object') {
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
            className="ml-2 px-2 py-1 bg-gray-200 rounded hover:bg-gray-300"
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
    <button className='submitButton' type="submit">登入</button>
  </form>

  <div>
    <a href="/forget-password">忘記密碼？</a>
    <a href="/register">註冊帳號</a>
  </div>

  <hr />

  <div>
    <p>其他登入方式</p>
    <button className='portal_submit_btn'>portal 登入</button>
  </div>
</div>
  <Sidebar />
</div>
  );
}
