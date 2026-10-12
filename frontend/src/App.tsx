/* 這裡都是寫頁面 */
import { Routes, Route } from 'react-router-dom';
import Start from './Start';
import Login from './pages/Login';
import Signup from './pages/Signup';
import ForgetPwd from './pages/ForgetPwd';
import VerifyEmail from './pages/VerifyEmail';
import Announcement from './pages/Announcement';
import Club from './pages/Club';
import Works from './pages/Works';
import { ComingSoon, NotFound } from './pages/StatusPage';
// 共用 Context
import { AuthProvider } from './contexts/AuthContext';
import { ChatProvider } from './contexts/ChatContext';

// AI 助理
import AssistantChat from './pages/AssistantChat';
import ChatWidget from './components/ChatWidget';

// import Notice from './pages/Notice';  // 之後要用再解註

export default function App() {
  return (
    <ChatProvider> {/* 讓 Routes 與 ChatWidget 都在提供者內 */}
      <div style={{ display: 'flex', minHeight: '100vh' }}>
        {/* <aside style={{ width: 200, padding: 20, background: '#f9f9f9' }}>
            <QuickNav />
          </aside> */}
          
        {/* 不要加 padding：各頁面都是 100vw / 100vh 滿版，加了會整頁多出捲軸 */}
        <main style={{ flex: 1, minWidth: 0 }}>
          <AuthProvider>
            <Routes>
              {/* Route 之後需要加密 */}
              <Route path="/" element={<Start />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Signup />} />
              <Route path="/forget-password" element={<ForgetPwd />} />
              <Route path="/verify-email" element={<VerifyEmail />} />
              <Route path="/announcement" element={<Announcement />} />
              <Route path="/club" element={< Club/>} />
              <Route path="/club/works" element={<Works/>}/>
              {/* --- AI 助理聊天頁 --- */}
              <Route path="/assistant" element={<AssistantChat />} />
              {/* 已放進導覽列、尚未完成的功能 */}
              <Route path="/songfest" element={<ComingSoon feature="歌謠祭平台" />} />
              <Route path="/calendar" element={<ComingSoon feature="行事曆" />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </AuthProvider>
        </main>
          
        {/* 全站浮動 AI 助理按鈕 / 面板 */}
        <ChatWidget />
        
      </div>
    </ChatProvider>
  );
}