-- Table: papers
-- Stores metadata and content for academic papers.
CREATE TABLE papers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    arxiv_id VARCHAR(50) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    authors JSONB NOT NULL,
    abstract TEXT NOT NULL,
    publication_date DATE NOT NULL,
    full_text TEXT,
    summaries JSONB,
    embedding_id VARCHAR(255),  -- Links to Pinecone embeddings
    related_papers JSONB,  -- Stores related papers from OpenAlex API
    tags JSONB  -- Stores paper tags directly
);

-- Table: items
-- Stores learning materials tied to papers. Deletes cascade from papers.
CREATE TABLE items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL,  -- e.g., 'quiz', 'text', 'flashcard'
    level VARCHAR(20) NOT NULL,  -- e.g., 'beginner', 'advanced'
    category VARCHAR(20) NOT NULL,  -- e.g., 'math', 'physics'
    data JSONB NOT NULL,  -- Stores specific content details
    "order" INTEGER NOT NULL,  -- For sequencing items
    videos JSONB  -- Stores video links if applicable
);

-- Table: questions
-- Stores verification questions for learning items, supporting multiple types.
CREATE TABLE questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    item_id UUID REFERENCES items(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL,  -- 'true_false', 'multiple_choice', 'free_response'
    text TEXT NOT NULL,  -- The question itself
    choices JSONB,  -- Options for multiple-choice (e.g., ["A", "B", "C"])
    correct_answer TEXT  -- 'true', 'A', or free-response answer
);

-- Table: answers
-- Records user responses to questions. Deletes cascade from auth.users and questions.
CREATE TABLE answers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    question_id UUID REFERENCES questions(id) ON DELETE CASCADE,
    answer TEXT NOT NULL,  -- User's response: 'true', 'B', or free text
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: progress
-- Tracks user progress on learning items with SPRT metrics.
CREATE TABLE progress (
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    item_id UUID REFERENCES items(id) ON DELETE CASCADE,
    status VARCHAR(20),  -- e.g., 'in_progress', 'completed'
    sprt_log_likelihood_ratio FLOAT DEFAULT 0.0,  -- SPRT metric
    decision VARCHAR(20),  -- e.g., 'mastered', 'needs_review'
    PRIMARY KEY (user_id, item_id)
);

-- Table: badges
-- Defines gamification badges.
CREATE TABLE badges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL,  -- e.g., 'Quiz Master'
    description TEXT  -- e.g., 'Completed 10 quizzes'
);

-- Table: achievements
-- Records badges awarded to users. Deletes cascade from auth.users, restricted from badges.
CREATE TABLE achievements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    badge_id UUID REFERENCES badges(id) ON DELETE RESTRICT,
    awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table: queries
-- Stores user questions and AI responses. Deletes cascade from auth.users and papers.
CREATE TABLE queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    answer_text TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance optimization
CREATE INDEX idx_items_paper_id ON items(paper_id);
CREATE INDEX idx_questions_item_id ON questions(item_id);
CREATE INDEX idx_answers_user_id ON answers(user_id);
CREATE INDEX idx_answers_question_id ON answers(question_id);
CREATE INDEX idx_progress_user_id ON progress(user_id);
CREATE INDEX idx_progress_item_id ON progress(item_id);
CREATE INDEX idx_achievements_user_id ON achievements(user_id);
CREATE INDEX idx_achievements_badge_id ON achievements(badge_id);
CREATE INDEX idx_queries_user_id ON queries(user_id);
CREATE INDEX idx_queries_paper_id ON queries(paper_id);
CREATE INDEX idx_papers_tags ON papers USING gin (tags);