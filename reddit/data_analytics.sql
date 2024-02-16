--all subreddits an author has posted to or commented in
SELECT post_author, subreddit
FROM (
    SELECT post_author, subreddit
    FROM post
    UNION
    SELECT comment_author as author_id, subreddit
    FROM comment
) AS subreddits_by_author
ORDER BY post_author, subreddit;
