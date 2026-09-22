import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Variants } from 'framer-motion';
import Sidebar from './Sidebar.tsx';
import NoticeBoard from './NoticeBoard.tsx';
import InfoBox from './InfoBox.tsx';
import '../styles/Home-p0.css';
import '../styles/Home-p1.css';
import '../styles/Home-p2.css';
import '../styles/Page-content.css';
import '../styles/Page-navigation.css';


const Home: React.FC = () => {
  const [currentPage, setCurrentPage] = useState(0);
  const [direction, setDirection] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);

  const pages = [
    {
      id: 0,
      title: '中央動畫社',
      classname: 'page-0'
    },
    {
      id: 1,
      title: '最新公告',
      classname: 'page-1'
    },
    {
      id: 2,
      title: '關於社團',
      classname: 'page-2'
    }
  ];

  const totalPages = pages.length;

  useEffect(() => {
    const handleScroll = (e: WheelEvent) => {
      e.preventDefault();
      if (isAnimating) return;

      const next = e.deltaY > 0 ? currentPage + 1 : currentPage - 1;
      if (next >= 0 && next < totalPages) {
        setDirection(e.deltaY > 0 ? 1 : -1);
        setCurrentPage(next);
        setIsAnimating(true);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown' || e.key === 'PageDown') {
        setCurrentPage(prev => Math.min(prev + 1, totalPages - 1));
      } else if (e.key === 'ArrowUp' || e.key === 'PageUp') {
        setCurrentPage(prev => Math.max(prev - 1, 0));
      }
    };

    window.addEventListener('wheel', handleScroll, { passive: false });
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('wheel', handleScroll);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [currentPage, isAnimating, totalPages]);

  const pageVariants: Variants = {
  enter: (direction: number) => ({
    y: direction > 0 ? 1000 : -1000,
    opacity: 0
  }),
  center: {
    y: 0,
    opacity: 1,
    transition: { duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }
  },
  exit: (direction: number) => ({
    y: direction > 0 ? -1000 : 1000,
    opacity: 0,
    transition: { duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }
  })
};

  const contentVariants = {
    initial: { opacity: 0, y: 50 },
    animate: {
      opacity: 1,
      y: 0,
      transition: { delay: 0.3, duration: 0.6, staggerChildren: 0.1 }
    }
  };

  const itemVariants = {
    initial: { opacity: 0, y: 30 },
    animate: { opacity: 1, y: 0 }
  };

  return (
    <div className={`page-container page-${currentPage}`}>
      
      {/* 側邊欄 */}
      <Sidebar />

      <AnimatePresence custom={direction}> {/* 🔧 傳遞 direction 給 variants */}
        <motion.div
          key={currentPage}
          className={`page-content ${pages[currentPage].classname}`}
          custom={direction}
          variants={pageVariants}
          initial="enter"
          animate="center"
          exit="exit"
          onAnimationComplete={() => setIsAnimating(false)}
        > 

          {/* 第一頁的背景物件(跟背景是一體的) */}
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}> {/*確保第一頁能順利切換*/}
          </motion.div>
          {currentPage === 0 && (
            <>
            <div className="p0-blue-box-border" /> {/* 藍色方塊外框 */}
            <div className="p0-green-circle-border" /> {/* 綠色圓形外框 */}
            <div className="p0-blue-box">
              <img src="/images/GBC_Nina.jpg" alt="GBC_Nina" className="p0-blue-box-img" />
            </div>
            <div className="p0-yellow-triangle"> {/* 黃色三角形 */}
              <img src="/images/三角初華.jpg" alt="三角初華" className="p0-yellow-triangle-img" /> {/* 黃色三角形內部圖片 */}
            </div>
            <div className="p0-green-circle"> {/* 綠色圓形 */}
              <img src="/images/原神啟動.jpg" alt="原神啟動" className="p0-green-circle-img" /> {/* 綠色圓形內部圖片 */}
            </div>
            </>
          )}

          {/* 第一頁的物件 */}
          <motion.div 
          className="p0-title-wrapper"
          variants={contentVariants} 
          initial="initial" 
          animate="animate">
            {currentPage === 0 && (

              /* 「中央動畫社」標題 */
              <h1 className="p0-outlined-text">  {/* 包住外框及填充 */}
                  <span className="p0-text-border">中央動畫社</span> {/* 黑色字體外框 */}
                  <span className="p0-text-fill">中央動畫社</span> {/* 白色字體填充 */}
              </h1>
            )}
          </motion.div>

          {/* 第二頁的背景物件(跟背景是一體的) */}
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}> {/*確保第二頁能順利切換*/}
          </motion.div>
          {currentPage === 1 && (
            <>
            <div className="p1-blue-box-small-border-0" /> {/* 藍色小方塊外框-0 */}
            <div className="p1-blue-box-small-border-1" /> {/* 藍色小方塊外框-1 */}
            <div className="p1-blue-box-small-border-2" /> {/* 藍色小方塊外框-2 */}
            <div className="p1-blue-box-small-0" /> {/* 藍色小方塊-0 */}
            <div className="p1-blue-box-small-1" /> {/* 藍色小方塊-1 */}
            <div className="p1-blue-box-small-2" /> {/* 藍色小方塊-2 */}
          
            </>
          )}

          {/* 第二頁的物件 */}
           {currentPage === 1 && (
          <motion.div
            className="p1-title-wrapper"
            variants={contentVariants}
            initial="initial"
            animate="animate"
          >
            {/* 「最新公告」標題 */}
            <div className="p1-announcement-wrapper">
              <div className="p1-blue-box-big" />
              <div className="p1-blue-box-big-border" /> {/* 藍色大方塊外框 */}
              <div className="p1-outlined-text">
              <span className="p1-text-border">最新公告</span>
              <span className="p1-text-fill">最新公告</span>
            </div>
          </div>

          </motion.div>
          )}

          {/* 公告欄組件 */}
          {currentPage === 1 && (
          <motion.div
            className="p1-notice-wrapper"
            variants={contentVariants}
            initial="initial"
            animate="animate"
          >
          <NoticeBoard />
          </motion.div>
          )}

          {/* 第三頁的背景物件(跟背景是一體的) */}
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}> {/*確保第三頁能順利切換*/}
          </motion.div>
          {currentPage === 2 && (
            <>
            <div className="p2-green-circle-big-border" /> {/* 綠色大圓形外框 */}
            <div className="p2-green-circle-small-border-0" /> {/* 綠色小圓形外框-0 */}
            <div className="p2-green-circle-small-border-1" /> {/* 綠色小圓形外框-1 */}
            <div className="p2-green-circle-big" /> {/* 綠色大圓形 */}
            <div className="p2-green-circle-small-0" /> {/* 綠色小圓形-0 */}
            <div className="p2-green-circle-small-1" /> {/* 綠色小圓形-1 */}

            </>
          )}
          {/* 第三頁的物件 */}
          {currentPage === 2 && (
            <motion.div
              className="p2-title-wrapper"
              variants={contentVariants}
              initial="initial"
              animate="animate"
            >
              {/* 「關於社團」標題 */}
            <h1 className="p2-outlined-text">
            <span className="p2-text-border">關於社團</span>
            <span className="p2-text-fill">關於社團</span>
            </h1>
            <motion.div
              className="p2-notice-wrapper"
              variants={contentVariants}
              initial="initial"
              animate="animate"
            >
              <InfoBox />
            </motion.div>
            </motion.div>
          )}
          
        </motion.div>


      {/* 導航提示 */}
        <motion.p className="navigation-hint" variants={itemVariants}>
          {currentPage === 0 && '向下滾動或按 ↓ 鍵繼續'}
          {currentPage === totalPages - 1 && '向上滾動或按 ↑ 鍵返回'}
          {currentPage > 0 && currentPage < totalPages - 1 && '使用滾輪或方向鍵導航'}
        </motion.p>
      </AnimatePresence>

      {/* 右側圓點導航 */}
      <div className="page-nav-dots-container">  {/* 圓點導航容器 */}
        {pages.map((_, index) => (
          <button
            key={index}
            onClick={() => setCurrentPage(index)}
            className={`page-nav-dots ${index === currentPage ? 'active' : ''}`} /* 當前頁面的導航圓點是否有 active 樣式 */
          />
        ))}
      </div>

    </div>
  );
};

export default Home;
