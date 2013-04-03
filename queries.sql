;
;
;
SELECT DISTINCT candidate
FROM contributions
ORDER BY candidate;


;
; total contribution amount by candidate
;
SELECT candidate, SUM(amount) as total_amount, COUNT(1) as contributions
FROM contributions
GROUP BY candidate
ORDER BY total_amount DESC;

;
; total contribution amount by contributor type
;
SELECT contributor_type, SUM(amount) as total_amount, COUNT(1) as contributions
FROM contributions
GROUP BY contributor_type
ORDER BY total_amount DESC;

;
; non-individual contributors
;
SELECT *
FROM contributions
WHERE contributor_type != 'Individual';

;
; contributions outside of DMV grouped by candidate
;
SELECT candidate, SUM(amount) as total_amount, COUNT(1) as contributions
FROM contributions
WHERE state not in ('DC', 'MD', 'VA')
GROUP BY candidate
ORDER BY total_amount DESC;

;
; top outside cities
;
SELECT city, SUM(amount) as total_amount, COUNT(1) as contributions
FROM contributions
WHERE state NOT IN ('DC', 'MD', 'VA')
GROUP BY city
ORDER BY total_amount DESC
LIMIT 10;
