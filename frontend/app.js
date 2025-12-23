const API_URL = "/api";
let gameId = null;
let liveGameState = null; // Represents the actual state on the server
let viewedGameState = null; // Represents what is currently being rendered (could be a past move)
let currentMoveIndex = 0; // The index of the move being viewed
let totalMoves = 0; // Total moves in the game so far
let selectedSpot = null;
let isRequestPending = false;

console.log("Bagh Chal App Loaded - Version 1.2 (History & Navigation)");

const boardGrid = document.getElementById('board-grid');
const statusDiv = document.getElementById('status');
const goatsPlacedSpan = document.getElementById('goats-placed');
const goatsCapturedSpan = document.getElementById('goats-captured');
const baghsTrappedSpan = document.getElementById('baghs-trapped');
const turnIndicator = document.getElementById('turn-indicator');
const messageLog = document.getElementById('message-log');
const moveHistoryDiv = document.getElementById('move-history');
const newGameBtn = document.getElementById('new-game-btn');
const undoBtn = document.getElementById('undo-btn');
const loadPgnBtn = document.getElementById('load-pgn-btn');
const uploadPgnBtn = document.getElementById('upload-pgn-btn');
const pgnFileInput = document.getElementById('pgn-file-input');

const rewindBtn = document.getElementById('rewind-btn');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const fastForwardBtn = document.getElementById('fast-forward-btn');

if (newGameBtn) newGameBtn.addEventListener('click', startNewGame);
if (undoBtn) undoBtn.addEventListener('click', undoMove);
if (loadPgnBtn) loadPgnBtn.addEventListener('click', loadGameFromPaste);
if (uploadPgnBtn) uploadPgnBtn.addEventListener('click', () => pgnFileInput.click());
if (pgnFileInput) pgnFileInput.addEventListener('change', handleFileUpload);


if (rewindBtn) rewindBtn.addEventListener('click', () => seekToMove(0));
if (prevBtn) prevBtn.addEventListener('click', () => seekToMove(currentMoveIndex - 1));
if (nextBtn) nextBtn.addEventListener('click', () => seekToMove(currentMoveIndex + 1));
if (fastForwardBtn) fastForwardBtn.addEventListener('click', () => seekToMove(totalMoves));

async function startNewGame() {
    if (isRequestPending) return;
    isRequestPending = true;
    updateUI();

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
    } finally {
        isRequestPending = false;
        updateUI();
    }
}

async function loadGameFromPaste() {
    const pgn = prompt("Paste PGN string:");
    if (pgn) {
        await executeLoad(pgn);
    }
}

async function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
        const pgn = e.target.result;
        await executeLoad(pgn);
    };
    reader.readAsText(file);
    // Clear input so same file can be uploaded again if needed
    event.target.value = '';
}

async function executeLoad(pgn) {
    if (isRequestPending) return;
    isRequestPending = true;
    updateUI();

    try {
        messageLog.innerText = "Loading Game...";
        const res = await fetch(`${API_URL}/games/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pgn: pgn })
        });

        if (!res.ok) {
            const err = await res.json();
            messageLog.innerText = err.detail || "Load Failed";
            isRequestPending = false;
            updateUI();
            return;
        }

        const data = await res.json();
        gameId = data.game_id;
        selectedSpot = null;
        messageLog.innerText = "Game Loaded Successfully!";
        await fetchGameState();
    } catch (e) {
        console.error(e);
        messageLog.innerText = "Error loading game.";
    } finally {
        isRequestPending = false;
        updateUI();
    }
}


async function fetchGameState() {
    if (!gameId) return;
    try {
        const res = await fetch(`${API_URL}/games/${gameId}`);
        const data = await res.json();
        liveGameState = data;
        const moves = parsePGN(liveGameState.pgn);
        totalMoves = moves.length;

        // When fetching the live state, jump to the end automatically
        await seekToMove(totalMoves, true);
    } catch (e) {
        console.error(e);
    }
}

async function seekToMove(index, silent = false) {
    if (!gameId || isRequestPending) return;
    if (index < 0) index = 0;
    if (index > totalMoves) index = totalMoves;

    currentMoveIndex = index;

    if (!silent) {
        messageLog.innerText = `Seeking to move ${currentMoveIndex}...`;
        isRequestPending = true;
        updateUI();
    }

    try {
        const res = await fetch(`${API_URL}/games/${gameId}/seek/${currentMoveIndex}`);
        if (!res.ok) {
            const err = await res.json();
            messageLog.innerText = err.detail || "Seek failed";
            return;
        }
        viewedGameState = await res.json();

        if (!silent) messageLog.innerText = viewedGameState.message || "Viewing Move";

        renderBoard();
        updateUI();
    } catch (e) {
        console.error(e);
        messageLog.innerText = "Seek Error";
    } finally {
        if (!silent) {
            isRequestPending = false;
            updateUI();
        }
    }
}
async function makeMove(moveStr) {
    if (!gameId || isRequestPending) return;
    isRequestPending = true;
    updateUI(); // Disable buttons

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
            isRequestPending = false;
            updateUI();
            renderBoard(); // clear selection
            return;
        }

        await fetchGameState(); // This will jump us to the end

        // Auto trigger bot if game is not over
        if (!liveGameState.game_over) {
             await triggerBotMove();
        }

    } catch (e) {
        console.error(e);
        messageLog.innerText = "Error making move.";
    } finally {
        isRequestPending = false;
        updateUI();
    }
}

async function triggerBotMove() {
    if (!gameId || isRequestPending) return; // Prevent bot from being re-triggered if something else is happening
    isRequestPending = true;
    updateUI();

    messageLog.innerText = "Thinking...";
    try {
        const res = await fetch(`${API_URL}/games/${gameId}/bot-move`, {
            method: 'POST'
        });
        await fetchGameState();
    } catch (e) {
        console.error(e);
        messageLog.innerText = "Bot Error.";
    } finally {
        isRequestPending = false;
        updateUI();
    }
}

async function undoMove() {
     if (!gameId || isRequestPending) return;
     isRequestPending = true;
     messageLog.innerText = "Undoing...";
     updateUI();

     try {
         const res = await fetch(`${API_URL}/games/${gameId}/undo`, {
             method: 'POST'
         });

         if (!res.ok) {
             const err = await res.json();
             messageLog.innerText = err.detail || "Cannot Undo";
             isRequestPending = false;
             updateUI();
             return;
         }

         const data = await res.json();
         liveGameState = data;
         const moves = parsePGN(liveGameState.pgn);
         totalMoves = moves.length;

         messageLog.innerText = liveGameState.message || "Undone";

         // Jump to the end of the new history
         await seekToMove(totalMoves, true);

     } catch (e) {
         console.error(e);
         messageLog.innerText = "Undo Error";
     } finally {
         isRequestPending = false;
         updateUI();
     }
}

function updateUI() {
    if (!viewedGameState) return;

    // Status and Info (based on viewed state)
    statusDiv.innerText = viewedGameState.game_over ?
        `Game Over! Winner: ${viewedGameState.winner}` :
        `Status: In Progress`;

    goatsPlacedSpan.innerText = viewedGameState.goats_placed;
    goatsCapturedSpan.innerText = viewedGameState.goats_captured;
    baghsTrappedSpan.innerText = viewedGameState.baghs_trapped;

    const turnText = viewedGameState.turn === 'G' ? "Goat" : "Tiger";
    turnIndicator.innerText = turnText;
    turnIndicator.style.color = viewedGameState.turn === 'G' ? 'black' : 'orange';

    // Buttons
    const buttonsDisabled = viewedGameState.game_over || isRequestPending;
    if (undoBtn) undoBtn.disabled = buttonsDisabled || totalMoves === 0;
    if (newGameBtn) newGameBtn.disabled = isRequestPending;

    if (rewindBtn) rewindBtn.disabled = isRequestPending || (currentMoveIndex === 0);
    if (prevBtn) prevBtn.disabled = isRequestPending || (currentMoveIndex === 0);
    if (nextBtn) nextBtn.disabled = isRequestPending || (currentMoveIndex === totalMoves);
    if (fastForwardBtn) fastForwardBtn.disabled = isRequestPending || (currentMoveIndex === totalMoves);

    // History Panel
    renderMoveHistory();
}

function renderMoveHistory() {
    if (!liveGameState) return;
    moveHistoryDiv.innerHTML = '';

    const moves = parsePGN(liveGameState.pgn);

    for (let i = 0; i < moves.length; i += 2) {
        const row = document.createElement('div');
        row.className = 'move-row';

        const num = document.createElement('span');
        num.className = 'move-num';
        num.innerText = Math.floor(i/2) + 1 + ".";
        row.appendChild(num);

        // White (Goat) move
        const m1 = document.createElement('span');
        m1.className = 'move-item';
        if (currentMoveIndex === i + 1) m1.classList.add('active');
        m1.innerText = moves[i];
        m1.addEventListener('click', () => seekToMove(i + 1));
        row.appendChild(m1);

        // Black (Tiger) move
        if (i + 1 < moves.length) {
            const m2 = document.createElement('span');
            m2.className = 'move-item';
            if (currentMoveIndex === i + 2) m2.classList.add('active');
            m2.innerText = moves[i+1];
            m2.addEventListener('click', () => seekToMove(i + 2));
            row.appendChild(m2);
        }

        moveHistoryDiv.appendChild(row);
    }

    // Auto scroll to active move
    const active = moveHistoryDiv.querySelector('.active');
    if (active) active.scrollIntoView({ block: 'nearest' });
}

function parsePGN(pgn) {
    if (!pgn) return [];
    return pgn.trim().split(/\s+/).filter(m => m.length > 0 && !m.endsWith('.'));
}

function renderBoard() {
    if (!viewedGameState || !viewedGameState.board) return;
    boardGrid.innerHTML = '';
    const board = viewedGameState.board;

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
            }

            boardGrid.appendChild(spotDiv);
        }
    }
}

function isSelected(r, c) {
    return selectedSpot && selectedSpot.r === r && selectedSpot.c === c;
}

function handleSpotClick(r, c, cellVal) {
    if (!viewedGameState || viewedGameState.game_over) return;

    // Only allow moves if we are viewing the latest state
    if (currentMoveIndex !== totalMoves) {
        messageLog.innerText = "Cannot move while viewing history. Use ⏩ to resume.";
        return;
    }

    const currentTurn = viewedGameState.turn;
    const placingPhase = (currentTurn === 'G' && viewedGameState.goats_placed < 20);

    if (placingPhase) {
        if (cellVal === "") {
            makeMove(`${r}${c}`);
        } else {
            messageLog.innerText = "Spot occupied!";
        }
        return;
    }

    if (!selectedSpot) {
        if (cellVal === currentTurn) {
            selectedSpot = { r, c };
            renderBoard();
            messageLog.innerText = "Piece Selected";
        } else if (cellVal !== "") {
            messageLog.innerText = "Not your piece!";
        }
    } else {
        if (r === selectedSpot.r && c === selectedSpot.c) {
            selectedSpot = null;
            renderBoard();
            messageLog.innerText = "Deselected";
        } else if (cellVal === currentTurn) {
            selectedSpot = { r, c };
            renderBoard();
            messageLog.innerText = "Selection Changed";
        } else if (cellVal === "") {
            const moveStr = `${selectedSpot.r}${selectedSpot.c}${r}${c}`;
            makeMove(moveStr);
        } else {
            messageLog.innerText = "Invalid destination";
        }
    }
}
