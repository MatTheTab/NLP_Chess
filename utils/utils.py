import chess.pgn
import zstandard
import io
import numpy as np
import os
from collections import deque
import pandas as pd
import chess.engine
import random
import gzip

def save_game_data(all_games_df, game_number, game, columns, engine, time_limit = 0.01):
    data = {}
    for col in columns:
        data[col] = []
    board = game.board()
    j=0
    white_elo = game.headers['WhiteElo']
    black_elo = game.headers['BlackElo']
    for move in game.mainline_moves():
        j+=1
        color = board.turn
        data, board = get_random_move(data, board, game_number, j, engine, color, time_limit, white_elo, black_elo)
        data, board = get_human_move(data, board, move, game_number, j, engine, color, time_limit, white_elo, black_elo)
    data_df = pd.DataFrame(data)
    if all_games_df.empty:
        all_games_df = data_df.copy()
    else:
        all_games_df = pd.concat([all_games_df, data_df], ignore_index=True)
    return all_games_df

def save_data(pgn_file_path, save_file_path, max_num_games, stockfish_path, shuffle=True, verbose = True, seed = 42):
    columns = ["game_number", "move_number", "board", "move", "legal", "stockfish_2", "stockfish_5", "stockfish_10", 
               "move_quality_2", "move_quality_5", "move_quality_10", "prev_ELO", "current_ELO",
                "real", "piece_placement", "active_color", "castling_availability", "en_passant", "halfmove_clock", "fullmove_number",
                "prev_board", "prev_piece_placement", "prev_active_color", "prev_castling_availability", "prev_en_passant", "prev_halfmove_clock", "prev_fullmove_number"]
    random.seed(seed)
    all_games_df = pd.DataFrame(columns=columns)
    done = False
    i = 0
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    with open(pgn_file_path, "rb") as compressed_file:
        dctx = zstandard.ZstdDecompressor()
        with dctx.stream_reader(compressed_file) as decompressed_file:
            while not done:
                chunk = decompressed_file.read(1024**3) #Read one GB at a time
                if not chunk:
                    break
                pgn_text = chunk.decode("utf-8")
                pgn_io = io.StringIO(pgn_text)
                while True:
                    pgn_game = chess.pgn.read_game(pgn_io)
                    if i >= max_num_games:
                        done = True
                        break
                    elif pgn_game is None:
                        break

                    all_games_df = save_game_data(all_games_df =  all_games_df, game_number = i, game = pgn_game, columns = columns, engine = engine)
                    i+=1
    if shuffle:
        all_games_df = all_games_df.sample(frac=1, random_state=seed).reset_index(drop=True)
    all_games_df.to_csv(save_file_path, index=False, compression="gzip")
    if verbose:
        print(f"Num processed games in a file = {i}")

def get_human_move(data, board, move, game_number, j, engine, color, time_limit, white_elo, black_elo):
    prev_board = board.fen()
    board.push(move)
    str_representation = board.fen()
    data["game_number"].append(game_number)
    data["move_number"].append(j)
    data["board"].append(str_representation)
    data["prev_board"].append(prev_board)
    data["move"].append(move.uci())
    data["legal"].append(True)
    score2, score5, score10 = get_stockfish_scores(board, engine, color, time_limit)
    data["stockfish_2"].append(score2)
    data["stockfish_5"].append(score5)
    data["stockfish_10"].append(score10)
    if j>2:
        data["move_quality_2"].append(data["stockfish_2"][-1] + data["stockfish_2"][-3])
        data["move_quality_5"].append(data["stockfish_5"][-1] + data["stockfish_5"][-3])
        data["move_quality_10"].append(data["stockfish_10"][-1] + data["stockfish_10"][-3])
    else:
        data["move_quality_2"].append(None)
        data["move_quality_5"].append(None)
        data["move_quality_10"].append(None)
    data["real"].append(True)
    temp_representation = str_representation.split()
    temp_prev_representation = prev_board.split()
    data["piece_placement"].append(temp_representation[0])
    data["active_color"].append(temp_representation[1])
    if temp_representation[1] == "b":
        data["prev_ELO"].append(white_elo)
        data["current_ELO"].append(black_elo)
    else:
        data["prev_ELO"].append(black_elo)
        data["current_ELO"].append(white_elo)
    data["castling_availability"].append(temp_representation[2])
    data["en_passant"].append(temp_representation[3])
    data["halfmove_clock"].append(temp_representation[4])
    data["fullmove_number"].append(temp_representation[5])

    data["prev_piece_placement"].append(temp_prev_representation[0])
    data["prev_active_color"].append(temp_prev_representation[1])
    data["prev_castling_availability"].append(temp_prev_representation[2])
    data["prev_en_passant"].append(temp_prev_representation[3])
    data["prev_halfmove_clock"].append(temp_prev_representation[4])
    data["prev_fullmove_number"].append(temp_prev_representation[5])

    return data, board

def get_random_move(data, board, game_number, j, engine, color, time_limit, white_elo, black_elo):
    prev_board = board.fen()
    possible_moves = get_pseudolegal_moves(board)
    legal_moves = list(board.legal_moves)
    random_move = random.choice(possible_moves)
    board.push(random_move)
    str_representation = board.fen()
    data["game_number"].append(game_number)
    data["move_number"].append(j)
    data["board"].append(str_representation)
    data["prev_board"].append(prev_board)
    data["move"].append(random_move.uci())
    if random_move in legal_moves:
        legal = True
    else:
        legal = False
    data["legal"].append(legal)
    if legal:
        score2, score5, score10 = get_stockfish_scores(board, engine, color, time_limit)
        data["stockfish_2"].append(score2)
        data["stockfish_5"].append(score5)
        data["stockfish_10"].append(score10)
        if j>2:
            data["move_quality_2"].append(data["stockfish_2"][-1] + data["stockfish_2"][-2])
            data["move_quality_5"].append(data["stockfish_5"][-1] + data["stockfish_5"][-2])
            data["move_quality_10"].append(data["stockfish_10"][-1] + data["stockfish_10"][-2])
        else:
            data["move_quality_2"].append(None)
            data["move_quality_5"].append(None)
            data["move_quality_10"].append(None)
    else:
        data["stockfish_2"].append(None)
        data["stockfish_5"].append(None)
        data["stockfish_10"].append(None)
        data["move_quality_2"].append(None)
        data["move_quality_5"].append(None)
        data["move_quality_10"].append(None)
    data["real"].append(False)
    temp_representation = str_representation.split()
    temp_prev_representation = prev_board.split()
    data["piece_placement"].append(temp_representation[0])
    data["active_color"].append(temp_representation[1])
    data["castling_availability"].append(temp_representation[2])
    data["en_passant"].append(temp_representation[3])
    data["halfmove_clock"].append(temp_representation[4])
    data["fullmove_number"].append(temp_representation[5])
    data["prev_ELO"].append(None)
    if temp_representation[1] == "b":
        data["current_ELO"].append(black_elo)
    else:
        data["current_ELO"].append(white_elo)
    
    data["prev_piece_placement"].append(temp_prev_representation[0])
    data["prev_active_color"].append(temp_prev_representation[1])
    data["prev_castling_availability"].append(temp_prev_representation[2])
    data["prev_en_passant"].append(temp_prev_representation[3])
    data["prev_halfmove_clock"].append(temp_prev_representation[4])
    data["prev_fullmove_number"].append(temp_prev_representation[5])

    board.pop()
    return data, board

def get_stockfish_scores(board, engine, color, time_limit):
    info_2 = engine.analyse(board, chess.engine.Limit(depth=2, time=time_limit))
    score_2 = info_2['score'].pov(color=color).score(mate_score=900)
    info_5 = engine.analyse(board, chess.engine.Limit(depth=5, time=time_limit))
    score_5 = info_5['score'].pov(color=color).score(mate_score=900)
    info_10 = engine.analyse(board, chess.engine.Limit(depth=10, time=time_limit))
    score_10 = info_10['score'].pov(color=color).score(mate_score=900)
    return score_2, score_5, score_10

def get_pseudolegal_moves(board):
    pseudolegal_moves = []
    for from_square in chess.SQUARES:
        if board.piece_at(from_square) is not None:
            for to_square in chess.SQUARES:
                pseudolegal_moves.append(chess.Move(from_square, to_square))
    return pseudolegal_moves