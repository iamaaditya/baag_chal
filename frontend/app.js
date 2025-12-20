const API_URL = "/api";
let gameId = null;
let gameState = null;
let selectedSpot = null;

const boardGrid = document.getElementById('board-grid');
const statusDiv = document.getElementById('status');
const goatsPlacedSpan = document.getElementById('goats-placed');
const goatsCapturedSpan = document.getElementById('goats-captured');
const baghsTrappedSpan = document.getElementById('baghs-trapped');
const turnIndicator = document.getElementById('turn-indicator');
const messageLog = document.getElementById('message-log');
const newGameBtn = document.getElementById('new-game-btn');
const botMoveBtn = document.getElementById('bot-move-btn');

newGameBtn.addEventListener('click', startNewGame);
botMoveBtn.addEventListener('click', triggerBotMove);

async function startNewGame() {
    try {
        const res = await fetch(`${API_URL}/games`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: 'PvC', difficulty: 3 })
        });
        const data = await res.json();
        gameId = data.game_id;
        selectedSpot = null;
        messageLog.innerText = "New Game Started!";
        await fetchGameState();
    } catch (e) {
        console.error(e);
        messageLog.innerText = "Error starting game.";
    }
}

async function fetchGameState() {
    if (!gameId) return;
    try {
        const res = await fetch(`${API_URL}/games/${gameId}`);
        gameState = await res.json();
        renderBoard();
        updateInfo();
    } catch (e) {
        console.error(e);
    }
}

async function makeMove(moveStr) {
    if (!gameId) return;
    try {
        const res = await fetch(`${API_URL}/games/${gameId}/move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ move: moveStr })
        });
        if (!res.ok) {
            const err = await res.json();
            messageLog.innerText = err.detail || "Invalid Move";
            selectedSpot = null;
            renderBoard(); // clear selection
            return;
        }
        gameState = await res.json();
        selectedSpot = null;
        messageLog.innerText = gameState.message || "Move made";
        renderBoard();
        updateInfo();
    } catch (e) {
        console.error(e);
        messageLog.innerText = "Error making move.";
    }
}

async function triggerBotMove() {
    if (!gameId) return;
    messageLog.innerText = "Thinking...";
    try {
        const res = await fetch(`${API_URL}/games/${gameId}/bot-move`, {
            method: 'POST'
        });
        gameState = await res.json();
        messageLog.innerText = gameState.message || "Bot moved";
        renderBoard();
        updateInfo();
    } catch (e) {
        console.error(e);
        messageLog.innerText = "Bot Error.";
    }
}

function updateInfo() {
    if (!gameState) return;
    statusDiv.innerText = gameState.game_over ? 
        `Game Over! Winner: ${gameState.winner}` : 
        `Status: In Progress`;
    
    goatsPlacedSpan.innerText = gameState.goats_placed;
    goatsCapturedSpan.innerText = gameState.goats_captured;
    baghsTrappedSpan.innerText = gameState.baghs_trapped;
    
    const turnText = gameState.turn === 'G' ? "Goat" : "Tiger";
    turnIndicator.innerText = turnText;
    turnIndicator.style.color = gameState.turn === 'G' ? 'black' : 'orange';

    botMoveBtn.disabled = gameState.game_over;
}

function renderBoard() {
    boardGrid.innerHTML = '';
    const board = gameState.board; // 5x5 array of strings "G", "B", or ""

    for (let r = 1; r <= 5; r++) {
        for (let c = 1; c <= 5; c++) {
            const cellVal = board[r-1][c-1];
            const spotDiv = document.createElement('div');
            spotDiv.className = 'spot';
            spotDiv.dataset.r = r;
            spotDiv.dataset.c = c;
            
            spotDiv.addEventListener('click', () => handleSpotClick(r, c, cellVal));

            if (cellVal === 'G') {
                const p = document.createElement('div');
                p.className = 'piece goat';
                p.innerText = 'G';
                spotDiv.appendChild(p);
                if (isSelected(r, c)) p.classList.add('selected');
            } else if (cellVal === 'B') {
                const p = document.createElement('div');
                p.className = 'piece tiger';
                p.innerText = 'T';
                spotDiv.appendChild(p);
                if (isSelected(r, c)) p.classList.add('selected');
            } else if (cellVal.startsWith('B') || cellVal.startsWith('G')) {
                // Should not happen with pure cleaning but just in case
            }

            // Highlight valid moves if a piece is selected?
            // (Optional, can calculate from possible_moves in gameState)

            boardGrid.appendChild(spotDiv);
        }
    }
}

function isSelected(r, c) {
    return selectedSpot && selectedSpot.r === r && selectedSpot.c === c;
}

function handleSpotClick(r, c, cellVal) {
    if (!gameState || gameState.game_over) return;

    const currentTurn = gameState.turn; // 'G' or 'B'
    const placingPhase = (currentTurn === 'G' && gameState.goats_placed < 20);

    // LOGIC
    if (placingPhase) {
        // Placement mode
        if (cellVal === "") {
            makeMove(`${r}${c}`);
        } else {
            messageLog.innerText = "Spot occupied!";
        }
        return;
    }

    // Moving Phase (or Tiger turn)
    if (!selectedSpot) {
        // Try to select
        if (cellVal === currentTurn) {
            selectedSpot = { r, c };
            renderBoard();
            messageLog.innerText = "Piece Selected";
        } else if (cellVal !== "") {
            messageLog.innerText = "Not your piece!";
        } else {
            // Clicked empty spot without selection
        }
    } else {
        // Already selected
        if (r === selectedSpot.r && c === selectedSpot.c) {
            // Deselect
            selectedSpot = null;
            renderBoard();
            messageLog.innerText = "Deselected";
        } else if (cellVal === currentTurn) {
            // Change selection
            selectedSpot = { r, c };
            renderBoard();
            messageLog.innerText = "Selection Changed";
        } else if (cellVal === "") {
            // Attempt move
            const moveStr = `${selectedSpot.r}${selectedSpot.c}${r}${c}`;
            makeMove(moveStr);
        } else {
            // Clicked opponent piece? Invalid unless capturing logic different
            messageLog.innerText = "Invalid destination";
        }
    }
}
