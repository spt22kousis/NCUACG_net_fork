import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
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