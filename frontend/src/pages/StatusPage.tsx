// frontend/src/pages/StatusPage.tsx
// 「建置中」與「找不到頁面」共用的簡單版面
import { Link } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import '../styles/StatusPage.css';

interface StatusPageProps {
  emoji: string;
  title: string;
  message: string;
}

function StatusPage({ emoji, title, message }: StatusPageProps) {
  return (
    <div className="status-page">
      <Sidebar />
      <div className="status-card">
        <div className="status-emoji" aria-hidden="true">{emoji}</div>
        <h1 className="status-title">{title}</h1>
        <p className="status-message">{message}</p>
        <Link to="/" className="status-home-link">回首頁</Link>
      </div>
    </div>
  );
}

/** 已經放進導覽列、但功能還沒做好的頁面 */
export function ComingSoon({ feature }: { feature: string }) {
  return (
    <StatusPage
      emoji="🛠️"
      title={`${feature}建置中`}
      message="這個功能還在開發，敬請期待！"
    />
  );
}

export function NotFound() {
  return (
    <StatusPage
      emoji="🔍"
      title="找不到這個頁面"
      message="網址可能打錯了，或是頁面已經搬家。"
    />
  );
}
