import React, { useState } from 'react';
import '../styles/Club.css';
import Sidebar from '../components/Sidebar';
import Introduction from './Introduction';
import introData from '../data/introduction.json'; // 正確引入 JSON 檔案
// 定義六邊形項目的資料結構
type HexItemType = 'button' | 'text' | 'image' | 'empty';

interface HexItem {
  id: number;
  type: HexItemType;
  label?: string;
  url?: string;
  imageSrc?: string;
}

// 你的初始資料
const initialHexItems: HexItem[] = [
  { id: 17, type: 'text', label: '社' },
  { id: 14, type: 'button', label: '動畫\n播放組', url: 'anime' },
  { id: 15, type: 'button', label: '御宅藝', url: 'otaku' },
  { id: 28, type: 'text', label: '課' },
  { id: 24, type: 'button', label: '模型\n製作', url: 'model' },
  { id: 25, type: 'button', label: '繪畫',url:'art' },
  { id: 26, type: 'button', label: 'TRPG', url: 'trpg' },
  { id: 22, type: 'text', label: '介' },
  { id: 34, type: 'button', label: 'MV\n剪輯', url: 'mv' },
  { id: 35, type: 'button', label: '聲優', url: 'seiyuu' },
  { id: 36, type: 'button', label: '鐵道', url: 'railway' },
  { id: 32, type: 'text', label: '紹' },
];

// 決定 hex grid 最大 ID
const MAX_ID = 50;

// 產生完整的 hexItems 陣列
const hexItems: HexItem[] = Array.from({ length: MAX_ID }, (_, i) => ({
  id: i + 1,
  type: 'empty' as HexItemType,
}));

// 把 initialHexItems 覆蓋進去（確保 id 與 index 一致）
initialHexItems.forEach(item => {
  hexItems[item.id - 1] = item;
});


const Club: React.FC = () => {
  const [activeHexId, setActiveHexId] = useState<number | null>(null);
  // modalContent 的類型現在是 JSON 陣列中的一個物件
  const [modalContent, setModalContent] = useState<typeof introData[0] | null>(null);

  const handleClick = (item: HexItem) => {
    if (item.type === 'button' && item.url) {
      setActiveHexId(item.id);
      // 在陣列中查找對應的物件
      const content = introData.find(contentItem => contentItem.url === item.url);
      if (content) {
        setModalContent(content);
      }
    }
  };
  
  const handleCloseModal = () => {
    setModalContent(null);
  };

  return (
    <div className="full-page-container">
      <Sidebar />
      <div className="hex-grid-container">
        {hexItems.map((item, index) => {
          const isButton = item.type === 'button';
          const isActive = activeHexId === item.id;
          const row = Math.floor(index / 10);
          const isOddRow = row % 2 === 1;
          
          return (
            <div 
              key={item.id} 
              className={`hex-item-wrapper ${isOddRow ? 'offset' : ''}`}
            >
              <div className='hex-item-border'>
                <div
                  className={`hex-item-content
                    ${item.type}
                    ${isButton ? 'is-button' : ''}
                    ${isActive ? 'active' : ''}`}
                  onClick={() => handleClick(item)}
                  style={!isButton ? { cursor: 'default' } : undefined}
                >
                  {/* ... 渲染內容部分保持不變 ... */}
                  {item.type === 'text' && (
                    item.label?.split('\n').map((line, index) => (
                      <span key={index}>{line}</span>
                    ))
                  )}
                  {item.type === 'button' && (
                    item.label?.split('\n').map((line, index) => (
                      <span key={index}>{line}</span>
                    ))
                  )}
                  {item.type === 'image' && item.imageSrc && (
                    <img src={item.imageSrc} alt="" style={{ maxWidth: '80%', maxHeight: '80%' }} />
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {/* 手機版：桌機的 10 欄蜂巢排不下，只列出社課按鈕（CSS 控制只在窄螢幕顯示） */}
      <div className="club-mobile-list">
        <h1 className="club-mobile-title">社課介紹</h1>
        <div className="club-mobile-grid">
          {initialHexItems.filter(item => item.type === 'button').map(item => (
            <button
              key={item.id}
              type="button"
              className={`club-mobile-hex ${activeHexId === item.id ? 'active' : ''}`}
              onClick={() => handleClick(item)}
            >
              {item.label?.replace(/\n/g, '')}
            </button>
          ))}
        </div>
      </div>
      {modalContent && (
        <Introduction
          content={modalContent}
          onClose={handleCloseModal}
        />
      )}
    </div>
  );
};

export default Club;