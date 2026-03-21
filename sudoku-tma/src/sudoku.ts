// Simple and working Sudoku Generator
function generateSudoku(difficulty: number): { puzzle: number[][]; solution: number[][] } {
  const BLANK = 0;
  
  // Create empty 9x9 grid
  const grid: number[][] = Array(9).fill(0).map(() => Array(9).fill(BLANK));
  
  // Fill diagonal 3x3 boxes (they don't affect each other)
  for (let boxRow = 0; boxRow < 9; boxRow += 3) {
    fillBox(grid, boxRow, boxRow);
  }
  
  // Solve to fill the rest
  solve(grid);
  
  // Make a copy for solution
  const solution = grid.map(row => [...row]);
  
  // Remove cells based on difficulty
  // Difficulty 1: remove 30, 2: remove 40, 3: remove 50, 4: remove 55
  const cellsToRemove = 25 + difficulty * 10;
  let removed = 0;
  let attempts = 0;
  
  while (removed < cellsToRemove && attempts < 500) {
    const row = Math.floor(Math.random() * 9);
    const col = Math.floor(Math.random() * 9);
    
    if (grid[row][col] !== BLANK) {
      const backup = grid[row][col];
      grid[row][col] = BLANK;
      
      // Check if unique solution still exists
      const testGrid = grid.map(r => [...r]);
      if (countSolutions(testGrid) === 1) {
        removed++;
      } else {
        grid[row][col] = backup;
      }
    }
    attempts++;
  }
  
  return { puzzle: grid, solution };
}

function fillBox(grid: number[][], row: number, col: number) {
  const nums = shuffle([1, 2, 3, 4, 5, 6, 7, 8, 9]);
  let n = 0;
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
      grid[row + i][col + j] = nums[n++];
    }
  }
}

function shuffle<T>(arr: T[]): T[] {
  const result = [...arr];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

function canPlace(grid: number[][], row: number, col: number, num: number): boolean {
  // Check row
  for (let x = 0; x < 9; x++) {
    if (grid[row][x] === num) return false;
  }
  // Check column
  for (let x = 0; x < 9; x++) {
    if (grid[x][col] === num) return false;
  }
  // Check 3x3 box
  const boxRow = Math.floor(row / 3) * 3;
  const boxCol = Math.floor(col / 3) * 3;
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
      if (grid[boxRow + i][boxCol + j] === num) return false;
    }
  }
  return true;
}

function solve(grid: number[][]): boolean {
  for (let row = 0; row < 9; row++) {
    for (let col = 0; col < 9; col++) {
      if (grid[row][col] === 0) {
        for (const num of shuffle([1, 2, 3, 4, 5, 6, 7, 8, 9])) {
          if (canPlace(grid, row, col, num)) {
            grid[row][col] = num;
            if (solve(grid)) return true;
            grid[row][col] = 0;
          }
        }
        return false;
      }
    }
  }
  return true;
}

function countSolutions(grid: number[][]): number {
  let count = 0;
  
  function solveCount(g: number[][]): boolean {
    for (let row = 0; row < 9; row++) {
      for (let col = 0; col < 9; col++) {
        if (g[row][col] === 0) {
          for (let num = 1; num <= 9; num++) {
            if (canPlace(g, row, col, num)) {
              g[row][col] = num;
              if (solveCount(g)) {
                g[row][col] = 0;
                if (++count > 1) return true;
              }
              g[row][col] = 0;
            }
          }
          return false;
        }
      }
    }
    return ++count >= 1;
  }
  
  solveCount(grid);
  return count;
}

export { generateSudoku };
