import type { DrawShape } from "@lichess-org/chessground/draw";
import { makeSquare, type NormalMove, parseUci } from "chessops";
import type { Position } from "chessops/chess";
import { match } from "ts-pattern";
import { arrowColors } from "../panels/analysis/BestMoves";
import {
    agreementArrowShape,
    getEngineAgreements,
    shortenAgreementArrow,
} from "./engineAgreementArrows";

const LARGE_BRUSH = 11;
const MEDIUM_BRUSH = 7.5;
const SMALL_BRUSH = 4;

export function getEngineArrowShapes({
    arrows,
    pos,
    showConsecutiveArrows,
    orientation,
    boardId,
    deferAgreements = false,
    additionalShapes = [],
}: {
    arrows: Map<number, { pv: string[]; winChance: number }[]>;
    pos: Position;
    showConsecutiveArrows: boolean;
    orientation: "white" | "black";
    boardId: string;
    deferAgreements?: boolean;
    additionalShapes?: DrawShape[];
}): DrawShape[] {
    const shapes: DrawShape[] = [];
    const entries = Array.from(arrows.entries()).sort((a, b) => a[0] - b[0]);

    for (const [i, moves] of entries) {
        if (i >= 4 || moves.length === 0) continue;

        const bestWinChance = moves[0].winChance;
        for (const [j, { pv, winChance }] of moves.entries()) {
            const posClone = pos.clone();
            let prevSquare = null;

            for (const [ii, uci] of pv.entries()) {
                const move = parseUci(uci);
                if (!move || !posClone.isLegal(move)) break;

                posClone.play(move);
                const normalMove = move as NormalMove;
                const from = makeSquare(normalMove.from)!;
                const to = makeSquare(normalMove.to)!;
                if (prevSquare === null) prevSquare = from;

                const brushSize = match(bestWinChance - winChance)
                    .when(
                        (difference) => difference < 2.5,
                        () => LARGE_BRUSH,
                    )
                    .when(
                        (difference) => difference < 5,
                        () => MEDIUM_BRUSH,
                    )
                    .otherwise(() => SMALL_BRUSH);

                if (ii !== 0 && !(showConsecutiveArrows && j === 0 && ii % 2 === 0)) continue;

                if (
                    ii < 5 &&
                    !shapes.some((shape) => shape.orig === from && shape.dest === to) &&
                    prevSquare === from
                ) {
                    shapes.push({
                        orig: from,
                        dest: to,
                        brush: j === 0 ? arrowColors[i].strong : arrowColors[i].pale,
                        modifiers: { lineWidth: brushSize },
                    });
                    prevSquare = to;
                } else {
                    break;
                }
            }
        }
    }

    if (deferAgreements) return shapes;

    for (const agreement of getEngineAgreements(arrows)) {
        const index = shapes.findIndex(
            (shape) => shape.orig === agreement.orig && shape.dest === agreement.dest,
        );
        if (index !== -1) {
            shapes[index] = agreementArrowShape(
                agreement.orig,
                agreement.dest,
                agreement.colors,
                orientation,
                boardId,
                {
                    lineWidth: shapes[index].modifiers?.lineWidth ?? LARGE_BRUSH,
                    opacities: agreement.opacities,
                    shorten: shortenAgreementArrow(agreement.dest, [
                        ...shapes,
                        ...additionalShapes,
                    ]),
                },
            );
        }
    }

    return shapes;
}
