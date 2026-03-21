import { useEffect, useState, useCallback } from 'react';
import { init } from '@telegram-apps/sdk-react';
import './App.css';

type Grid = number[][];
type Difficulty = 1 | 2 | 3 | 4;

const DIFFICULTY_NAMES: Record<Difficulty, string> = {
  1: '簡單', 2: '中等', 3: '困難', 4: '專家'
};

const PUZZLES = [
  { puzzle: [[5,3,0,0,7,0,0,0,0],[6,0,0,1,9,5,0,0,0],[0,9,8,0,0,0,0,6,0],[8,0,0,0,6,0,0,0,3],[4,0,0,8,0,3,0,0,1],[7,0,0,0,2,0,0,0,6],[0,6,0,0,0,0,2,8,0],[0,0,0,4,1,9,0,0,5],[0,0,0,0,8,0,0,7,9]], solution: [[5,3,4,6,7,8,9,1,2],[6,7,2,1,9,5,3,4,8],[1,9,8,3,4,2,5,6,7],[8,5,9,7,6,1,4,2,3],[4,2,6,8,5,3,7,9,1],[7,1,3,9,2,4,8,5,6],[9,6,1,5,3,7,2,8,4],[2,8,7,4,1,9,6,3,5],[3,4,5,2,8,6,1,7,9]] },
  { puzzle: [[0,0,0,6,0,0,4,0,0],[7,0,0,0,0,3,6,0,0],[0,0,0,0,9,1,0,8,0],[0,0,0,0,0,0,0,0,0],[0,5,0,1,8,0,0,0,6],[6,0,0,9,0,0,0,0,0],[0,4,0,2,0,0,0,6,0],[9,0,3,0,0,0,0,0,0],[0,2,0,0,0,0,1,0,0]], solution: [[5,8,1,6,7,2,4,3,9],[7,9,2,8,4,3,6,1,5],[3,6,4,5,9,1,7,8,2],[1,3,9,4,6,5,8,2,7],[4,5,8,1,2,7,9,3,6],[6,7,2,9,3,8,5,4,1],[8,4,5,2,1,9,3,6,7],[9,1,3,7,5,6,2,4,8],[2,6,7,3,8,4,1,5,9]] },
  { puzzle: [[0,0,0,0,0,0,0,0,0],[0,0,0,0,0,3,0,8,5],[0,0,1,0,2,0,0,0,0],[0,0,0,5,0,7,0,0,0],[0,0,4,0,0,0,1,0,0],[0,9,0,0,0,0,0,0,0],[5,0,0,0,0,0,0,7,3],[0,0,2,0,1,0,0,0,0],[0,0,0,0,4,0,0,0,9]], solution: [[9,8,7,6,5,4,3,2,1],[2,4,6,1,7,3,9,8,5],[3,5,1,9,2,8,7,4,6],[1,2,8,5,3,7,6,9,4],[6,3,4,8,9,2,1,5,7],[7,9,5,4,6,1,8,3,2],[5,1,9,2,8,6,4,7,3],[4,7,2,3,1,9,5,6,8],[8,6,3,7,4,5,2,1,9]] },
  { puzzle: [[0,2,0,0,0,0,0,0,0],[0,0,0,6,0,0,0,0,3],[0,7,4,0,8,0,0,0,0],[0,0,0,0,0,3,0,0,2],[0,8,0,0,4,0,0,1,0],[6,0,0,5,0,0,0,0,0],[0,0,0,0,1,0,7,8,0],[5,0,0,0,0,9,0,0,0],[0,0,0,0,0,0,0,4,0]], solution: [[1,2,6,4,3,7,9,5,8],[8,9,5,6,2,4,1,7,3],[3,7,4,1,8,5,2,9,6],[4,5,7,9,6,3,8,1,2],[9,8,3,2,4,1,5,6,7],[6,1,2,5,7,8,4,3,9],[2,4,9,3,1,6,7,8,5],[5,3,8,7,9,9,6,2,1],[7,6,1,8,5,2,3,4,9]] }
];

function generateSudoku(difficulty: number) {
  const idx = Math.min(difficulty - 1, PUZZLES.length - 1);
  const p = PUZZLES[idx];
  return { puzzle: p.puzzle.map(r => [...r]), solution: p.solution.map(r => [...r]) };
}

function useTimer() {
  const [seconds, setSeconds] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  useEffect(() => {
    let interval: number;
    if (isRunning) interval = window.setInterval(() => setSeconds(s => s + 1), 1000);
    return () => clearInterval(interval);
  }, [isRunning]);
  const start = useCallback(() => setIsRunning(true), []);
  const pause = useCallback(() => setIsRunning(false), []);
  const reset = useCallback(() => { setSeconds(0); setIsRunning(false); }, []);
  const formatTime = () => `${Math.floor(seconds/60).toString().padStart(2,'0')}:${(seconds%60).toString().padStart(2,'0')}`;
  return { seconds, isRunning, start, pause, reset, formatTime };
}

function useStorage<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try { return JSON.parse(localStorage.getItem(key) || '') || initial; } catch { return initial; }
  });
  const save = useCallback((v: T) => { setValue(v); localStorage.setItem(key, JSON.stringify(v)); }, [key]);
  return [value, save] as const;
}

function App() {
  const [isReady, setIsReady] = useState(false);
  const [gameState, setGameState] = useState<'menu' | 'playing' | 'won'>('menu');
  const [difficulty, setDifficulty] = useState<Difficulty>(1);
  const [puzzle, setPuzzle] = useState<Grid>([]);
  const [solution, setSolution] = useState<Grid>([]);
  const [userGrid, setUserGrid] = useState<Grid>([]);
  const [selectedCell, setSelectedCell] = useState<{row: number; col: number} | null>(null);
  const [showNotes, setShowNotes] = useState(false);
  const [hints, setHints] = useState(3);
  const [mistakes, setMistakes] = useState(0);
  const [toast, setToast] = useState<string | null>(null);
  const timer = useTimer();
  const [bestTimes, setBestTimes] = useStorage<Record<Difficulty, number>>('sudoku-best', {1:0,2:0,3:0,4:0});
  const BLANK = 0;

  useEffect(() => { (async () => { try { await init(); } catch {} setIsReady(true); })(); }, []);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 2000); };

  const startGame = useCallback((diff: Difficulty) => {
    const { puzzle: p, solution: s } = generateSudoku(diff);
    setPuzzle(p); setSolution(s); setUserGrid(p.map(r => [...r]));
    setSelectedCell(null); setHints(3); setMistakes(0); setGameState('playing');
    timer.reset(); timer.start(); setDifficulty(diff);
  }, [timer]);

  const handleCellClick = useCallback((row: number, col: number) => {
    if (puzzle[row][col] !== BLANK) return;
    setSelectedCell({ row, col });
  }, [puzzle]);

  const handleNumberInput = useCallback((num: number) => {
    if (!selectedCell || gameState !== 'playing') return;
    const { row, col } = selectedCell;
    if (puzzle[row][col] !== BLANK) return;
    
    const newGrid = userGrid.map(r => [...r]);
    if (showNotes) {
      // Toggle note - simplified
      setShowNotes(false);
    } else {
      const prev = newGrid[row][col];
      newGrid[row][col] = num;
      setUserGrid(newGrid);
      
      if (num !== solution[row][col]) {
        setMistakes(m => { const n = m + 1; if (n >= 3) { timer.pause(); setGameState('won'); } return n; });
        showToast('❌ 錯誤!');
      } else if (prev === BLANK) {
        showToast('✅ 正確!');
      }
      
      if (newGrid.every((r, ri) => r.every((c, ci) => c === solution[ri][ci]))) {
        timer.pause();
        setGameState('won');
        const newBest = { ...bestTimes };
        if (!newBest[difficulty] || timer.seconds < newBest[difficulty]) {
          newBest[difficulty] = timer.seconds;
          setBestTimes(newBest);
          showToast('🎉 新紀錄!');
        }
      }
    }
  }, [selectedCell, showNotes, gameState, puzzle, solution, timer, bestTimes, difficulty, bestTimes, setBestTimes, userGrid]);

  const handleErase = useCallback(() => {
    if (!selectedCell || puzzle[selectedCell.row][selectedCell.col] !== BLANK) return;
    const newGrid = userGrid.map(r => [...r]);
    newGrid[selectedCell.row][selectedCell.col] = BLANK;
    setUserGrid(newGrid);
  }, [selectedCell, puzzle, userGrid]);

  const handleHint = useCallback(() => {
    if (!selectedCell || hints <= 0 || puzzle[selectedCell.row][selectedCell.col] !== BLANK) return;
    const newGrid = userGrid.map(r => [...r]);
    newGrid[selectedCell.row][selectedCell.col] = solution[selectedCell.row][selectedCell.col];
    setUserGrid(newGrid); setHints(h => h - 1); showToast('💡 提示!');
    if (newGrid.every((r, ri) => r.every((c, ci) => c === solution[ri][ci]))) { timer.pause(); setGameState('won'); }
  }, [selectedCell, hints, puzzle, solution, userGrid, timer]);

  const getCellClass = useCallback((row: number, col: number) => {
    let cls = 'cell';
    if (puzzle[row][col] !== BLANK) cls += ' fixed';
    if (selectedCell?.row === row && selectedCell?.col === col) cls += ' selected';
    if (userGrid[row][col] !== BLANK && userGrid[row][col] !== solution[row][col]) cls += ' error';
    if (selectedCell) {
      if (userGrid[row][col] !== BLANK && userGrid[row][col] === userGrid[selectedCell.row][selectedCell.col]) cls += ' highlight-same';
      if (row === selectedCell.row || col === selectedCell.col || (Math.floor(row/3) === Math.floor(selectedCell.row/3) && Math.floor(col/3) === Math.floor(selectedCell.col/3))) cls += ' highlight';
    }
    return cls;
  }, [puzzle, selectedCell, userGrid, solution]);

  if (!isReady) return <div className="loading">載入中...</div>;

  return (
    <div className="app">
      {toast && <div className="toast">{toast}</div>}
      
      {gameState === 'menu' && (
        <div className="menu">
          <div className="logo">🎮</div>
          <h1>數獨</h1>
          <p className="subtitle">Sudoku</p>
          <div className="difficulty">
            <h2>選擇難度</h2>
            {([1, 2, 3, 4] as Difficulty[]).map(d => (
              <button key={d} className="diff-btn" onClick={() => startGame(d)}>
                <span>{DIFFICULTY_NAMES[d]}</span>
                {bestTimes[d] && <span className="best">🏆 {Math.floor(bestTimes[d]/60)}:{String(bestTimes[d]%60).padStart(2,'0')}</span>}
              </button>
            ))}
          </div>
        </div>
      )}
      
      {gameState === 'playing' && (
        <div className="game">
          <div className="game-header">
            <button className="icon-btn" onClick={() => { if (confirm('確定退出?')) { timer.pause(); setGameState('menu'); }}}>←</button>
            <div className="game-info">
              <div className="timer">{timer.formatTime()}</div>
              <div className="lives">{'❤️'.repeat(Math.max(0, 3 - mistakes))}</div>
            </div>
            <button className="icon-btn" onClick={handleHint} disabled={hints <= 0}>💡{hints}</button>
          </div>
          
          <div className="board">
            {Array(9).fill(null).map((_, row) => (
              <div key={row} className="row">
                {Array(9).fill(null).map((_, col) => (
                  <div key={`${row}-${col}`} className={getCellClass(row, col)} onClick={() => handleCellClick(row, col)}>
                    {userGrid[row][col] || ''}
                  </div>
                ))}
              </div>
            ))}
          </div>
          
          <div className="controls">
            <div className="numpad">
              {[1,2,3,4,5,6,7,8,9].map(n => (
                <button key={n} className="num-btn" onClick={() => handleNumberInput(n)} disabled={!selectedCell}>{n}</button>
              ))}
            </div>
            <div className="actions">
              <button className="action-btn" onClick={() => setShowNotes(!showNotes)}>📝 {showNotes ? '開' : '關'}</button>
              <button className="action-btn" onClick={handleErase} disabled={!selectedCell}>⌫</button>
            </div>
          </div>
        </div>
      )}
      
      {gameState === 'won' && (
        <div className="won">
          <div className="trophy">{mistakes >= 3 ? '😢' : '🏆'}</div>
          <h1>{mistakes >= 3 ? '挑戰失敗' : '恭喜!'}</h1>
          {mistakes < 3 && <p className="time">{timer.formatTime()}</p>}
          <p className="diff">{DIFFICULTY_NAMES[difficulty]}</p>
          <div className="won-btns">
            <button onClick={() => startGame(difficulty)}>再玩一次</button>
            <button className="secondary" onClick={() => setGameState('menu')}>返回</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
