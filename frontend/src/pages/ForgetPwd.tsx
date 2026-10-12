// frontend/src/pages/ForgetPwd.tsx
// 線上重設密碼需要能寄信的信箱（SMTP），目前還沒有，先請使用者聯絡幹部處理。
// 原本的頁面是假流程：驗證碼由前端自己產生並印在 console，任何人都看得到。
import { Link } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import '../styles/Login.css';

const CLUB_EMAIL = 'ncuacg.tw@gmail.com';

export default function ForgetPwd() {
  return (
    <div className="outercontainer">
      <div className="submitForm-container">
        <h2 className="loginText">忘記密碼</h2>
        <p>線上重設密碼功能還在準備中。</p>
        <p>
          如果忘記密碼，請聯絡社團幹部協助處理，可以在社團 Discord 私訊幹部，
          或寄信到社團信箱 <a href={`mailto:${CLUB_EMAIL}`}>{CLUB_EMAIL}</a>，
          並附上你註冊時使用的 email。
        </p>
        <Link to="/login">回登入頁</Link>
      </div>
      <Sidebar />
    </div>
  );
}
