// frontend/src/pages/club/ClubLayout.tsx
// 社課公告、行事曆共用的外框：側邊欄按鈕、標題與分頁籤（樣式沿用歌謠祭頁面）
import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import Sidebar from '../../components/Sidebar';
import { useAuth } from '../../contexts/auth';
import '../../styles/Songfest.css';
import '../../styles/Lessons.css';

const TABS = [
  { to: '/club/lessons', label: '社課公告', end: true },
  { to: '/calendar', label: '行事曆', end: true },
];

export default function ClubLayout({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  // 社課負責人不一定是幹部，後端 /api/me/ 會另外告訴我們
  const canManage = Boolean(user?.courseLead) || user?.role === 'admin' || user?.role === 'superadmin';
  const tabs = canManage ? [...TABS, { to: '/club/lessons/manage', label: '管理社課公告', end: true }] : TABS;
  return (
    <div className="songfest-page">
      <Sidebar />
      <div className="songfest-inner">
        <header className="songfest-header">
          <p className="songfest-kicker">中央大學動畫社</p>
          <h1 className="songfest-title">社課與活動</h1>
          <nav className="songfest-tabs" aria-label="社課與活動">
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
