// frontend/src/pages/songfest/SongfestLayout.tsx
// 歌謠祭各頁共用的外框：側邊欄按鈕、標題與分頁籤
import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import Sidebar from '../../components/Sidebar';
import { useAuth } from '../../contexts/auth';
import '../../styles/Songfest.css';

const TABS = [
  { to: '/songfest', label: '首頁', end: true },
  { to: '/songfest/library', label: '舊曲清單', end: false },
  { to: '/songfest/setlists', label: '歌單瀏覽', end: false },
  { to: '/songfest/requests', label: '點歌', end: false },
  { to: '/songfest/submit', label: '新曲投稿', end: false },
  { to: '/songfest/guest', label: '亂入投稿', end: false },
];

export default function SongfestLayout({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  // 排歌組成員不一定是幹部，後端 /api/me/ 會另外告訴我們
  const isStaff = Boolean(user?.songfestStaff) || user?.role === 'admin' || user?.role === 'superadmin';
  const tabs = isStaff ? [...TABS, { to: '/songfest/manage', label: '管理歌單', end: false }] : TABS;
  return (
    <div className="songfest-page">
      <Sidebar />
      <div className="songfest-inner">
        <header className="songfest-header">
          <p className="songfest-kicker">中央大學動畫社</p>
          <h1 className="songfest-title">中央歌謠祭</h1>
          <nav className="songfest-tabs" aria-label="歌謠祭">
            {tabs.map(tab => (
              <NavLink
                key={tab.to}
                to={tab.to}
                end={tab.end}
                className={({ isActive }) => `songfest-tab${isActive ? ' is-active' : ''}`}
              >
                {tab.label}
              </NavLink>
            ))}
          </nav>
        </header>
        {children}
      </div>
    </div>
  );
}
