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
import { NotFound } from './pages/StatusPage';
import SongfestHome from './pages/songfest/SongfestHome';
import Library from './pages/songfest/Library';
import { SetlistDetail, SetlistIndex } from './pages/songfest/Setlists';
import Submit from './pages/songfest/Submit';
import Guest from './pages/songfest/Guest';
import Manage from './pages/songfest/Manage';
import Requests from './pages/songfest/Requests';
import Lessons, { LessonDetail } from './pages/club/Lessons';
import LessonManage from './pages/club/LessonManage';
import Calendar from './pages/club/Calendar';
import Photos from './pages/club/Photos';
import WorksManage from './pages/club/WorksManage';
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
              <Route path="/club/works/manage" element={<WorksManage />} />
              <Route path="/photos" element={<Photos />} />
              <Route path="/club/lessons" element={<Lessons />} />
              <Route path="/club/lessons/manage" element={<LessonManage />} />
              <Route path="/club/lessons/:id" element={<LessonDetail />} />
              <Route path="/calendar" element={<Calendar />} />
              {/* --- AI 助理聊天頁 --- */}
              <Route path="/assistant" element={<AssistantChat />} />
              {/* 歌謠祭 */}
              <Route path="/songfest" element={<SongfestHome />} />
              <Route path="/songfest/library" element={<Library />} />
              <Route path="/songfest/setlists" element={<SetlistIndex />} />
              <Route path="/songfest/setlists/:id" element={<SetlistDetail />} />
              <Route path="/songfest/submit" element={<Submit />} />
              <Route path="/songfest/guest" element={<Guest />} />
              <Route path="/songfest/manage" element={<Manage />} />
              <Route path="/songfest/requests" element={<Requests />} />
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