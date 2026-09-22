import { useState } from 'react';
import Sidebar from '../components/Sidebar';
export default function ForgetPwd() {
  const [useremail, setUsername] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [sentCode, setSentCode] = useState('');
  const [codeSent, setCodeSent] = useState(false);
  const [verified, setVerified] = useState(false);
  const [sending_error, setSendingError] = useState('');
  const [verify_error, setVerifyError] = useState('');

  const generateRandomCode = () => {
    return Math.floor(100000 + Math.random() * 900000).toString(); // 6位數字
  };

  const sendVerificationCode = () => {
    //可以加一個寄出失敗的可能
    const code = generateRandomCode();
    setSentCode(code);
    setCodeSent(true);
    setSendingError('');
    console.log(`模擬寄出驗證碼到 ${useremail}：${code}`); // 假裝有寄出去 測試用 處理完刪掉
  };

  const handleResetPassword = (e: React.FormEvent) => {
    e.preventDefault();
    if (!useremail) {
      setVerifyError('你的Email咧?');
      return;
    }
    if (!codeSent) {
      setVerifyError('請先寄送驗證碼');
      return;
    }
    if (verificationCode === sentCode) {
      setVerified(true);
      setVerifyError('');
    } else {
      setVerifyError('驗證碼錯誤');
    }
  };

  return (
    <div className="outercontainer">
      <h2 style={{ textAlign: 'center', marginBottom: '20px' }}>密碼重設</h2>
      <form onSubmit={handleResetPassword} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <input
          type="text"
          placeholder="請輸入你的電子郵件"
          value={useremail}
          onChange={(e) => setUsername(e.target.value)}
          style={{ padding: '10px', fontSize: '16px', borderRadius: '5px', border: '1px solid #ccc' }}
        />
        <button
          type="button"
          onClick={sendVerificationCode}
          style={{
            padding: '10px',
            backgroundColor: '#007bff',
            color: '#fff',
            fontSize: '16px',
            border: 'none',
            borderRadius: '5px',
            cursor: 'pointer'
          }}
        >
          寄送驗證碼
        </button>
        <input
          type="password"
          placeholder="驗證碼，如114514"
          value={verificationCode}
          onChange={(e) => setVerificationCode(e.target.value)}
          style={{ padding: '10px', fontSize: '16px', borderRadius: '5px', border: '1px solid #ccc' }}
        />      
        {sending_error && <div style={{ color: 'red', fontSize: '14px' }}>{sending_error}</div>}
        <button
          type="submit"
          style={{
            padding: '10px',
            backgroundColor: '#007bff',
            color: '#fff',
            fontSize: '16px',
            border: 'none',
            borderRadius: '5px',
            cursor: 'pointer'
          }}
        >
          輸入驗證碼
        </button>
        {verify_error && <div style={{ color: 'red', fontSize: '14px' }}>{verify_error}</div>}
        {verified && <div style={{ color: 'green', fontSize: '14px' }}>驗證成功！</div>}
      </form>
      <Sidebar/>
    </div>
    
  );
}