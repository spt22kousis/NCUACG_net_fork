import React from 'react';
import '../styles/InfoBox.css';
import aboutInfoRaw from '../data/aboutInfo.json';
// TODO: 把本地Json改成從資料庫抓公告資料

// 定義 JSON 資料型別（新格式）
type AboutItem = {
  source?: string;   // e.g. "about"
  section?: number;  // e.g. 0, 1, 2...
  content: string;   // 實際文字內容
};

// 兼容：若是舊版（純字串陣列），轉成 AboutItem[]
const normalizeAbout = (data: unknown): AboutItem[] => {
  if (Array.isArray(data)) {
    return data.map((it, idx) => {
      if (typeof it === 'string') {
        return { source: 'about', section: idx, content: it };
      }
      // 容錯：如果已是物件且有 content 就直接使用
      if (it && typeof it === 'object' && 'content' in it) {
        const obj = it as { source?: unknown; section?: unknown; content?: unknown };
        return {
          source: typeof obj.source === 'string' ? obj.source : 'about',
          section: typeof obj.section === 'number' ? obj.section : idx,
          content: String(obj.content ?? ''),
        };
      }
      // 其他型別，轉字串
      return { source: 'about', section: idx, content: String(it ?? '') };
    });
  }
  return [];
};

const aboutInfo = normalizeAbout(aboutInfoRaw);

const InfoBox: React.FC = () => {
  if (!aboutInfo.length) {
    return <div className="info-box"><p className="info-item">（暫無介紹內容）</p></div>;
  }

  return (
    <div className="info-box">
      {aboutInfo.map((item) => (
        <p
          key={`${item.source ?? 'about'}-${item.section ?? 0}-${item.content.slice(0,16)}`}
          className="info-item"
        >
          {item.content}
        </p>
      ))}
    </div>
  );
};

export default InfoBox;
