--all subreddits an author has posted to or commented in
SELECT author_id, subreddit
FROM (
    SELECT author_id, subreddit
    FROM post
    UNION
    SELECT comment_author as author_id, subreddit
    FROM comment
) AS subreddits_by_author
ORDER BY author_id, subreddit;
