

WITH news AS (
	SELECT * FROM (VALUES 
		%(articles)s
	) AS articles(hash_identifier,published_date,source_ref,title_head,compression)
	
)
INSERT INTO news_article(hash_identifier,published_date,source_ref,title_head,compression)
SELECT hash_identifier, published_date, source_ref, title_head, compression 
FROM news 
WHERE NOT EXISTS (SELECT 1 FROM news_article na WHERE na.hash_identifier = news.hash_identifier);

--COMMIT;

DELETE FROM news_article WHERE hash_identifier = ANY(%(remove_hashes)s) RETURNING hash_identifier; -- return the hashes that were deleted for db purposes & smooth exec