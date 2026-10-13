import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link, useNavigate } from 'react-router-dom';
import { fetchLessons, formatLessonTime, lessonLabel, type Lesson } from '../api/club';
import '../styles/Introduction.css';

// 定義新的 props 介面
interface IntroductionContent {
  title: string;
  text: string;
  url: string;   // 社課種類代碼，用來連到該種類的成果牆
  image?: string;
}

interface IntroductionProps {
  content: IntroductionContent;
  onClose: () => void;
}

const Introduction: React.FC<IntroductionProps> = ({ content, onClose }) => {
  const navigate = useNavigate();
  // 這個社課的下一堂（還沒結束的第一堂）；undefined 是載入中，null 是沒有排定
  const [next, setNext] = useState<Lesson | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    fetchLessons(content.url)
      .then(list => {
        const now = Date.now();
        const upcoming = list.find(l => new Date(l.endTime ?? l.startTime).getTime() >= now);
        if (!cancelled) setNext(upcoming ?? null);
      })
      .catch(() => { if (!cancelled) setNext(null); });
    return () => { cancelled = true; };
  }, [content.url]);

  return (
    <AnimatePresence>
      <motion.div
        className="modal-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className="modal-container"
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.8, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="modal-header">
            {content.title}
          </div>
          
          <div className="modal-content-list" style={{ backgroundImage: content.image ? `url(${content.image})` : 'none' }}>
            {/* 根據你的新 JSON 結構，渲染 text 內容 */}
            {content.text.split('\n').map((line, index) => (
              <div key={index} className="modal-content-item">
                {line}
              </div>
            ))}
          </div>

          <div className="modal-next-lesson">
            <strong>下一堂</strong>
            {next === undefined && <span>載入中…</span>}
            {next === null && <span>還沒有排定</span>}
            {next && (
              <Link to={`/club/lessons/${next.id}`}>
                {formatLessonTime(next)}｜{next.location}｜{lessonLabel(next)}
              </Link>
            )}
            <Link to={`/club/lessons?category=${content.url}`} className="modal-all-lessons">所有堂次 →</Link>
          </div>
          
          <div className="modal-footer">
            <button onClick={onClose} aria-label="關閉">
              <span role="img" aria-hidden="true">↩️</span>
            </button>
            <span className="nav-text">查看這個社課的成果</span>
            <button
              onClick={() => navigate(`/club/works?category=${content.url}`)}
              aria-label="前往成果牆"
            >
              <span role="img" aria-hidden="true">➡️</span>
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default Introduction;