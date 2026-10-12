import React, { useState, useEffect, } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Home from './components/Home.tsx';
import './Start.css';

// 開場動畫每個瀏覽階段（分頁）只播一次，之後回首頁直接進內容
const SPLASH_SEEN_KEY = 'ncuacg.splashSeen';

function splashAlreadySeen(): boolean {
  try {
    return sessionStorage.getItem(SPLASH_SEEN_KEY) === '1';
  } catch {
    return false;
  }
}

const Start: React.FC = () => {
  const [showSplash, setShowSplash] = useState(() => !splashAlreadySeen());

  useEffect(() => {
    if (!showSplash) return;
    const timer = setTimeout(() => {
      setShowSplash(false);
      try {
        sessionStorage.setItem(SPLASH_SEEN_KEY, '1');
      } catch {
        /* 無痕模式等情況寫不進去，下次照樣播 */
      }
    }, 2000);     // 2秒後消失

    return () => clearTimeout(timer);
  }, [showSplash]);

  return (
    <AnimatePresence mode="wait">
      {showSplash ? (
        <motion.div
          /* 顯示啟動動畫 */
          key="splash"
          initial={{ opacity: 1 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 1 }}
          className="splash-screen"
        >
          {/* 顯示動畫社logo */}
          <motion.img
            src="/images/logo.jpg"
            alt="Logo"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 1.0, ease: "easeOut" }}
            className="splash-logo"
          />
        </motion.div>
      ) : (
        <Home key="Home" />
      )}
    </AnimatePresence>
  );
};

export default Start;